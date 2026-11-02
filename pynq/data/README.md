# 数据与参考

`trash_weight/` 为新TAR的106份little-endian float32权重，文件名统一小写，字节/SHA不变。`model_manifest.json` 的name字段与实际路径一致；加载器转换为int16 Q10。

`peripherals/`、`samples/`、`captures/` 保留新TAR原始内容。后续Save新增采样不自动计为Detect同一帧，不由类别分数推算准确率。运行后新增文件会使原交付校验清单出现差异。

六类顺序及预处理见model_manifest与src/trash_pynq/model.py；本轮未重新训练或改权重、阈值、采样内容。
