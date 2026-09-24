# 作者：晨星
"""网络唯一出口：闸门 + ``trust_env=False`` 的 httpx 工厂 + Ollama 生命周期（ARCH C8 / F-11 / F-12）。

硬约束：
    * 任何指向 localhost 的 ``httpx.Client`` 必须 ``trust_env=False``（本机有 SOCKS5 代理，
      否则报 WinError 10054）；
    * ``HELIOS_ALLOW_NETWORK=0`` 时访问非本地地址必须抛 ``E_*_NET_DISABLED``；
    * Ollama 子进程用 ``subprocess.Popen`` 自包含拉起与回收，禁止 ``Start-Process``
      （沙箱 job object 会杀子进程）。
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import time

from collections.abc import Iterator, Mapping
from typing import Any

import httpx

from .errors import HeliosError, NetworkDisabledError


#: 环境变量名。
ENV_ALLOW_NETWORK: str = "HELIOS_ALLOW_NETWORK"
ENV_OLLAMA_HOST: str = "HELIOS_OLLAMA_HOST"

#: 默认 Ollama 地址。
DEFAULT_OLLAMA_HOST: str = "http://127.0.0.1:11434"

#: 视为本机的主机名集合。
LOCALHOST_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1", "[::1]"})

#: 真值字符串集合（大小写不敏感）。
TRUTHY: frozenset[str] = frozenset({"1", "true", "yes", "on"})

#: 默认请求超时（秒）。
DEFAULT_TIMEOUT_S: float = 10.0


def _env_mapping(env: Mapping[str, str] | None) -> Mapping[str, str]:
    """返回环境变量视图；未显式传入时使用进程环境。"""
    return os.environ if env is None else env


def network_allowed(env: Mapping[str, str] | None = None) -> bool:
    """读取网络闸门；默认关闭（offline 档）。"""
    raw = _env_mapping(env).get(ENV_ALLOW_NETWORK, "0")
    return raw.strip().lower() in TRUTHY


def ollama_host(env: Mapping[str, str] | None = None) -> str:
    """读取 Ollama 地址，缺省 ``http://127.0.0.1:11434``。"""
    return _env_mapping(env).get(ENV_OLLAMA_HOST, DEFAULT_OLLAMA_HOST).strip() or DEFAULT_OLLAMA_HOST


def is_localhost(url: str) -> bool:
    """判断 URL 是否指向本机（无 scheme 的输入按 host 处理）。"""
    candidate = url
    if "://" in candidate:
        candidate = candidate.split("://", 1)[1]
    host = candidate.split("/", 1)[0].split(":", 1)[0].strip().lower()
    return host in LOCALHOST_HOSTS


def guard(url: str, component: str = "core", env: Mapping[str, str] | None = None) -> None:
    """出网闸门：非本地地址且闸门关闭时抛 ``E_*_NET_DISABLED``。"""
    if is_localhost(url):
        return
    if not network_allowed(env):
        raise NetworkDisabledError(component=component, url=url)


def build_client(
    base_url: str = "",
    timeout_s: float = DEFAULT_TIMEOUT_S,
    headers: dict[str, str] | None = None,
) -> httpx.Client:
    """构造 httpx 客户端；**强制** ``trust_env=False``（F-11）。"""
    return httpx.Client(
        base_url=base_url,
        timeout=httpx.Timeout(timeout_s),
        headers=headers,
        trust_env=False,
    )


def build_async_client(
    base_url: str = "",
    timeout_s: float = DEFAULT_TIMEOUT_S,
    headers: dict[str, str] | None = None,
) -> httpx.AsyncClient:
    """异步版本，同样强制 ``trust_env=False``。"""
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(timeout_s),
        headers=headers,
        trust_env=False,
    )


def request(
    client: httpx.Client,
    method: str,
    url: str,
    component: str = "core",
    env: Mapping[str, str] | None = None,
    **kwargs: Any,
) -> httpx.Response:
    """经闸门发起请求；非本地地址在闸门关闭时抛错。"""
    guard(url, component=component, env=env)
    return client.request(method, url, **kwargs)


def ping(url: str, timeout_s: float = 1.0) -> bool:
    """探测地址可达性，异常一律视为不可达。"""
    with build_client(timeout_s=timeout_s) as client:
        try:
            response = client.get(url)
        except httpx.HTTPError:
            return False
        return response.status_code < 500


@contextlib.contextmanager
def ollama_session(
    host: str | None = None,
    startup_timeout_s: float = 20.0,
    poll_interval_s: float = 0.5,
    env: Mapping[str, str] | None = None,
) -> Iterator[httpx.Client]:
    """Ollama 服务生命周期上下文：按需拉起 -> 轮询就绪 -> 业务 -> ``finally`` 回收（F-12）。

    Raises:
        HeliosError: 闸门关闭或多次等待仍未就绪时抛 ``E_LLM_MODEL_MISSING``。
    """
    resolved = host or ollama_host(env)
    if not is_localhost(resolved):
        guard(resolved, component="llm", env=env)

    client = build_client(base_url=resolved, timeout_s=max(2.0, startup_timeout_s))
    try:
        if _tags_ready(client):
            yield client
            return

        guard(resolved, component="llm", env=env)
        process = _spawn_ollama()
        deadline = time.monotonic() + max(0.0, startup_timeout_s)
        ready = False
        try:
            while time.monotonic() < deadline:
                time.sleep(poll_interval_s)
                if _tags_ready(client):
                    ready = True
                    break
            if not ready:
                raise HeliosError(
                    code="E_LLM_MODEL_MISSING",
                    message=f"Ollama 在 {startup_timeout_s}s 内未就绪",
                    detail={"host": resolved},
                    recoverable=True,
                )
            yield client
        finally:
            _terminate(process)
    finally:
        client.close()


def _tags_ready(client: httpx.Client) -> bool:
    """轮询 Ollama ``/api/tags`` 判断就绪。"""
    try:
        response = client.get("/api/tags")
    except httpx.HTTPError:
        return False
    return response.status_code == 200


def _spawn_ollama() -> subprocess.Popen[bytes]:
    """以 Popen 拉起 ``ollama serve``（不使用 shell，不使用 Start-Process）。"""
    creation_flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=creation_flags,
    )


def _terminate(process: subprocess.Popen[bytes]) -> None:
    """优雅回收子进程：terminate -> 短等 -> kill。"""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        process.kill()
