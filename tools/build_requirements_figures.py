"""Build reproducible figures for the expanded requirements report."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".qa" / "requirements-figures"
MANIFEST = ROOT / "assets" / "image_search_queries" / "manifest.json"
FONT = Path("C:/Windows/Fonts/msyh.ttc")


def font(size: int):
    return ImageFont.truetype(str(FONT), size)


def contact_sheet() -> None:
    rows = json.loads(MANIFEST.read_text(encoding="utf-8"))["images"]
    groups = ["TABLE", "PENDANT", "FLOOR", "WALL", "CEILING"]
    labels = {"TABLE": "台灯", "PENDANT": "吊灯", "FLOOR": "落地灯", "WALL": "壁灯", "CEILING": "顶装灯具"}
    width, height = 1500, 1450
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    for row_no, group in enumerate(groups):
        selected = [item for item in rows if item["preliminary_category"] == group]
        y = row_no * 286
        draw.text((12, y + 98), labels[group], fill="#20364a", font=font(27))
        for col_no, item in enumerate(selected):
            x = 150 + col_no * 450
            source = Image.open(MANIFEST.parent / item["file"]).convert("RGB")
            thumb = ImageOps.contain(source, (380, 235))
            image.paste(thumb, (x + (380 - thumb.width) // 2, y + (235 - thumb.height) // 2))
            draw.rectangle((x - 4, y - 4, x + 384, y + 240), outline="#b8c2ca", width=2)
            draw.text((x + 4, y + 247), str(item["source_photo_id"]), fill="#333333", font=font(23))
    image.save(OUT / "query_contact_sheet.png")


def arrow(draw, xy, color="#3c6f92", width=5):
    (x1, y1), (x2, y2) = xy
    draw.line((x1, y1, x2, y2), fill=color, width=width)
    import math
    angle = math.atan2(y2 - y1, x2 - x1)
    size = 15
    for offset in (0.55, -0.55):
        px = x2 - size * math.cos(angle + offset)
        py = y2 - size * math.sin(angle + offset)
        draw.line((x2, y2, px, py), fill=color, width=width)


def box(draw, xy, title, subtitle=None, fill="#eaf1f5", border="#315976"):
    draw.rounded_rectangle(xy, radius=14, fill=fill, outline=border, width=3)
    x1, y1, x2, y2 = xy
    bbox = draw.textbbox((0, 0), title, font=font(28))
    tx = (x1 + x2 - (bbox[2] - bbox[0])) / 2
    draw.text((tx, y1 + 18), title, fill="#1e3448", font=font(28))
    if subtitle:
        bbox = draw.textbbox((0, 0), subtitle, font=font(20))
        sx = (x1 + x2 - (bbox[2] - bbox[0])) / 2
        draw.text((sx, y1 + 59), subtitle, fill="#455665", font=font(20))


def image_search_flow() -> None:
    canvas = Image.new("RGB", (1700, 760), "white")
    d = ImageDraw.Draw(canvas)
    boxes = [
        (35, 115, 265, 225, "顾客", "参考图片"),
        (320, 115, 580, 225, "输入校验", "格式与内容"),
        (635, 115, 925, 225, "特征检索", "召回与排序"),
        (985, 115, 1295, 225, "业务过滤", "上架 报价 库存"),
        (1350, 115, 1660, 225, "候选结果", "Top K 与详情"),
    ]
    for x1, y1, x2, y2, title, sub in boxes:
        box(d, (x1, y1, x2, y2), title, sub)
    for x1, x2 in [(265, 320), (580, 635), (925, 985), (1295, 1350)]:
        arrow(d, ((x1, 170), (x2 - 7, 170)))
    box(d, (595, 385, 970, 505), "商品图片特征索引", "图像 特征 模型版本", fill="#f4f6f8")
    box(d, (1040, 385, 1420, 505), "商品与报价数据", "在售状态 有效期 库存", fill="#f4f6f8")
    box(d, (635, 585, 1030, 700), "检索记录", "查询 ID 版本 耗时 结果", fill="#f4f6f8")
    arrow(d, ((785, 385), (785, 235)))
    arrow(d, ((1230, 385), (1140, 235)))
    d.line(((925, 235), (1000, 280), (1000, 570)), fill="#3c6f92", width=5)
    arrow(d, ((1000, 570), (1000, 580)))
    canvas.save(OUT / "image_search_data_flow.png")


def order_flow() -> None:
    canvas = Image.new("RGB", (1700, 760), "white")
    d = ImageDraw.Draw(canvas)
    boxes = [
        (35, 105, 270, 215, "顾客", "SKU 报价 地址"),
        (325, 105, 625, 215, "订单校验", "核价 库存 幂等"),
        (680, 105, 985, 215, "订单与快照", "待确认"),
        (1040, 105, 1340, 215, "商家处理", "确认 或 拒绝"),
        (1395, 105, 1660, 215, "履约结果", "发货 完成 评价"),
    ]
    for x1, y1, x2, y2, title, sub in boxes:
        box(d, (x1, y1, x2, y2), title, sub)
    for x1, x2 in [(270, 325), (625, 680), (985, 1040), (1340, 1395)]:
        arrow(d, ((x1, 160), (x2 - 7, 160)))
    box(d, (320, 400, 660, 525), "当前报价与库存", "提交时再次读取", fill="#f4f6f8")
    box(d, (735, 400, 1090, 525), "订单状态与快照", "成交价 地址 状态轨迹", fill="#f4f6f8")
    box(d, (1165, 400, 1510, 525), "发货凭证与评价", "受控访问 已购校验", fill="#f4f6f8")
    arrow(d, ((490, 400), (490, 225)))
    arrow(d, ((835, 225), (900, 390)))
    arrow(d, ((1250, 225), (1330, 390)))
    d.text((50, 645), "商家拒绝或发货前按规则取消：订单转已取消，记录原因并释放库存；系统不处理真实支付。", fill="#454545", font=font(24))
    canvas.save(OUT / "order_data_flow.png")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    contact_sheet()
    image_search_flow()
    order_flow()
    print(OUT)
