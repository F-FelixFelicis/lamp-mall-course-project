# 图搜评测数据与人工标注

此处固定 20 张商品图库照片和 15 张独立查询照片的路径、来源与 SHA-256。查询图按每类采集顺序固定划分：第一张用于开发集，共 5 张；其余为测试集，共 10 张。两种方法使用同一图库和相同划分，不用测试标注调参。图库、查询图的原始来源 ID 和文件哈希没有交集；dHash 距离不超过 4 的自动近重复候选为 0，仍需人工核查。

`dataset.json` 是冻结清单，`annotation.html` 是本地人工标注页面。直接在浏览器打开 HTML，即可并排查看参考图和按 SKU 编码排列的 20 张图库照片。页面不显示模型排序，避免标注受算法结果引导。

两名组员分别填写自己的代号，并对各查询图的全部 20 个 SKU 判断相关性：2 为强相关，1 为弱相关，0 为不相关。灯型相同不自动等于强相关。每张查询图须核对来源和近重复情况；目标过小或无法判断时，填写排除原因。可以随时导出进度，再导入继续。

两人的相关性或排除意见有分歧时，由第三名组员在同一页面导入其中一份、修改为裁定结果并填写具体理由，导出独立裁定文件。正式评测脚本只把 2 当作二值强相关；无相关项的查询单独统计，不进入 Recall 的平均分母。

三个 `*.template.json` 只是空白记录格式，尚未完成人工标注。不能将它们、粗分类标签、同源变换图或当前模型分数当作人工真值。

```powershell
python tools/prepare_image_benchmark.py
python tools/evaluate_image_search.py --predict-only --split dev
python tools/evaluate_image_search.py --predict-only --split test
# 两人完成标注，解决分歧后执行正式比较：
python tools/evaluate_image_search.py --review-a 路径/review-a.json --review-b 路径/review-b.json --adjudication 路径/adjudication.json --split test
```

没有分歧时可省略 `--adjudication`。正式模式遇到空白、版本不匹配、同一标注人、缺少 SKU 或未裁定的分歧都会停止；`--predict-only` 仅导出真实排序与离线耗时，`relevance_metrics` 明确为 `null`。输出默认位于忽略目录 `.qa/m4-benchmark`。

图片保留各自原有许可，不因本目录而改变。来源及摄影师见数据清单，原许可见相应照片页。标注人使用组内代号即可，不必填写姓名、电话等个人信息。

来源核对记录：2026-10-29 发现旧目录中 W02、T03 复用了 W01 的来源页地址，已按现有下载编号分别校正为 Pexels 8243139、8263858 的来源入口。页面在线核对遇到平台访问验证，`source_note` 和标注页明确提示仍需人工复核；没有宣称在线验证成功。图片字节与 SKU 未变。初次未标注清单已归档至 `.qa/m4-benchmark/dataset-history`，当前空白模板已更新为新数据版本。之前的计时记录对应初次清单版本，正式评测应重新运行当前版本。
