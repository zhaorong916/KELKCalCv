"""公共选项数据初始化脚本

用法:
    python seed_public_options.py

将前端 COMMON_DATA 常量迁移到数据库 public_options 表。
数据来源: 前端 Calculation.vue 的 COMMON_DATA 常量。
幂等执行: 同 (group_key, value) 已存在则跳过。
"""
import sys
sys.path.insert(0, r'd:\KELK办公\信息化工作\207 自研系统\KELKCalCv\backend')

from app.core.database import Base, engine, SessionLocal
from app.models import PublicOption

# 建表 (checkfirst=True, 幂等)
Base.metadata.create_all(bind=engine, checkfirst=True)

# 与前端 Calculation.vue COMMON_DATA 保持一致
PUBLIC_OPTIONS = {
    'connection_type': {
        'label': '连接形式',
        'options': ['法兰连接', '对夹连接', '对焊连接', '支耳连接', '螺纹连接', '卡套连接', '卡箍连接', '内自紧连接'],
    },
    'face_type': {
        'label': '密封面形式',
        'options': ['FF', 'RF', 'RJ', 'M', 'FM', 'T', 'G', 'BW', 'SW'],
    },
    'flange_standard': {
        'label': '法兰标准',
        'options': ['HG/T 20592-2009', 'HG/T 20615-2009', 'HG/T 20623-2009(A)', 'HG/T 20623-2009(B)', 'ASME B16.5'],
    },
    'body_material': {
        'label': '阀体材质',
        'options': ['A216M-WCB', 'A217M-WC6', 'A217M-WC9', 'LCB', 'A351M-CF8', 'A351M-CF8M',
                    'A351M-CF3', 'A351M-CF3M', '304', '316', '304L', '316L', '321', '347',
                    '310S', 'CD4MCU', 'Alloy 20#', 'WCB'],
    },
    'bonnet_material': {
        'label': '阀盖材质',
        'options': ['与阀体相同', 'A216M-WCB', '304', '316', '316L', 'A182-F11', 'A182-F22'],
    },
    'bonnet_form': {
        'label': '阀盖形式',
        'options': ['标准型', '散热片型', '加长型', '波纹管型', '蒸汽夹套型', '低温型加冷箱'],
    },
    'jacket_connection': {
        'label': '夹套连接',
        'options': ['NON', 'Rc1/2"', 'NPT1/2"', 'DN25'],
    },
    'packing_type': {
        'label': '填料类型',
        'options': ['标准型', '双重密封', '动态密封', '双重动态密封'],
    },
    'packing_material': {
        'label': '填料材质',
        'options': ['PTFE', 'PTFE(禁油)', '柔性石墨'],
    },
    'trim_material': {
        'label': '阀芯材质',
        'options': ['304', '304L', '304/部分堆STL.6', '304/全堆STL.6', '316', '316L',
                    '316/部分堆STL.6', '316/全堆STL.6', '17-4PH/H1025', 'XM-19/HT',
                    'Inconel718/HT', 'CD4MCU'],
    },
    'seat_material': {
        'label': '阀座材质',
        'options': ['PTFE', 'Nylon 66', '外部轴承型', '固体镶嵌轴承(铜合金基体)', 'Alloy 20#'],
    },
    'sleeve_material': {
        'label': '套筒材质',
        'options': ['304', '304L', '316', '316L', 'CF8', 'CF8M'],
    },
    'stem_material': {
        'label': '阀杆材质',
        'options': ['410', '410/HT', '316', '316L', 'A182-F11', 'A182-F11/HT', 'Inconel X-750/HT'],
    },
    'balance_seal_ring': {
        'label': '平衡密封环',
        'options': ['PTFE', 'PPL', '304/Ni55', '316/Ni55', '310S/Ni55', '304/F46', '316/F46', 'Alloy 20#'],
    },
}


def seed():
    db = SessionLocal()
    inserted = 0
    skipped = 0
    for group_key, info in PUBLIC_OPTIONS.items():
        for idx, value in enumerate(info['options']):
            exists = db.query(PublicOption).filter(
                PublicOption.group_key == group_key,
                PublicOption.value == value,
            ).first()
            if exists:
                skipped += 1
                continue
            row = PublicOption(
                group_key=group_key,
                value=value,
                label=value,
                sort_order=idx,
                is_active=True,
            )
            db.add(row)
            inserted += 1
    db.commit()
    print(f"public_options 初始化完成: 新增 {inserted}, 跳过 {skipped} (已存在)")
    db.close()


if __name__ == '__main__':
    seed()
