# Faiss 向量索引

Faiss 是 Meta 开源的高效相似度检索库，专注于稠密向量的近邻搜索。

IndexFlatIP 执行精确内积检索，当向量 L2 归一后等价于余弦相似度。

当向量规模超过数万时，可切换 IndexIVFFlat 以获得更高吞吐，代价是少量召回损失。

Faiss 提供 CPU 与 GPU 两种执行后端，并支持标量量化以压缩内存。
