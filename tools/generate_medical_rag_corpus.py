from __future__ import annotations

import argparse
import math
from collections import Counter
from datetime import date
from pathlib import Path


SYSTEMS = [
    {
        "name": "呼吸系统",
        "common_symptoms": ["咳嗽", "咳痰", "发热", "鼻塞", "流涕", "咽痛", "喘息", "胸闷"],
        "common_tests": ["体温和血氧饱和度评估", "血常规和C反应蛋白", "胸部X线或CT", "病原学检测", "肺功能检查"],
        "urgent_signs": ["呼吸困难", "口唇发绀", "持续高热", "血氧下降", "咯血", "意识改变"],
        "care": ["休息和补液", "避免烟雾刺激", "根据病因进行抗感染或抗炎治疗", "按医嘱使用吸入药物", "监测症状变化"],
        "departments": ["呼吸内科", "全科医学科", "急诊科"],
        "keywords": ["呼吸道", "感染", "咳嗽", "气道", "肺部"],
        "diseases": [
            "普通感冒", "流行性感冒", "急性支气管炎", "社区获得性肺炎", "慢性阻塞性肺疾病",
            "支气管哮喘", "过敏性鼻炎", "急性咽炎", "急性扁桃体炎", "肺结核",
            "支气管扩张", "肺栓塞", "胸膜炎", "阻塞性睡眠呼吸暂停", "新型冠状病毒感染",
        ],
    },
    {
        "name": "心血管系统",
        "common_symptoms": ["胸痛", "心悸", "气短", "乏力", "头晕", "下肢水肿", "活动耐量下降"],
        "common_tests": ["血压测量", "心电图", "心肌损伤标志物", "心脏超声", "血脂和血糖", "动态心电图"],
        "urgent_signs": ["压榨样胸痛", "大汗", "晕厥", "严重气短", "一侧肢体无力", "血压极高伴头痛"],
        "care": ["控制血压血脂血糖", "戒烟限酒", "规律运动和体重管理", "遵医嘱使用心血管药物", "定期复诊"],
        "departments": ["心血管内科", "急诊科", "全科医学科"],
        "keywords": ["心脏", "血管", "血压", "胸痛", "心律"],
        "diseases": [
            "高血压", "冠状动脉粥样硬化性心脏病", "稳定型心绞痛", "急性冠脉综合征", "心力衰竭",
            "房颤", "室上性心动过速", "早搏", "高脂血症", "动脉粥样硬化",
            "心肌炎", "心包炎", "瓣膜性心脏病", "下肢静脉血栓", "主动脉夹层风险评估",
        ],
    },
    {
        "name": "消化系统",
        "common_symptoms": ["腹痛", "腹胀", "恶心", "呕吐", "反酸", "腹泻", "便秘", "黑便"],
        "common_tests": ["腹部查体", "血常规和肝肾功能", "大便常规", "腹部超声", "胃镜或肠镜", "幽门螺杆菌检测"],
        "urgent_signs": ["呕血", "黑便", "剧烈腹痛", "腹膜刺激征", "持续呕吐", "黄疸加重", "脱水"],
        "care": ["清淡饮食", "补液和电解质管理", "避免酒精和刺激性食物", "根据病因用药", "必要时内镜或外科评估"],
        "departments": ["消化内科", "普外科", "急诊科"],
        "keywords": ["胃肠道", "肝胆胰", "腹痛", "消化", "内镜"],
        "diseases": [
            "胃食管反流病", "慢性胃炎", "消化性溃疡", "幽门螺杆菌感染", "急性胃肠炎",
            "肠易激综合征", "便秘", "脂肪肝", "胆囊结石", "急性胆囊炎",
            "急性胰腺炎", "病毒性肝炎", "肝硬化", "炎症性肠病", "痔疮",
        ],
    },
    {
        "name": "内分泌与代谢",
        "common_symptoms": ["口渴", "多尿", "体重变化", "乏力", "怕冷或怕热", "心悸", "出汗", "水肿"],
        "common_tests": ["空腹血糖和糖化血红蛋白", "甲状腺功能", "血脂", "尿常规", "肝肾功能", "电解质"],
        "urgent_signs": ["意识障碍", "严重低血糖", "酮症酸中毒表现", "甲亢危象表现", "严重脱水"],
        "care": ["饮食和运动管理", "体重管理", "规律监测指标", "遵医嘱调整药物", "筛查并发症"],
        "departments": ["内分泌科", "全科医学科", "营养科"],
        "keywords": ["血糖", "甲状腺", "代谢", "肥胖", "血脂"],
        "diseases": [
            "2型糖尿病", "1型糖尿病", "糖尿病前期", "低血糖", "甲状腺功能亢进",
            "甲状腺功能减退", "甲状腺结节", "痛风", "高尿酸血症", "肥胖症",
            "代谢综合征", "骨质疏松症", "维生素D缺乏", "库欣综合征风险评估", "多囊卵巢综合征代谢问题",
        ],
    },
    {
        "name": "神经系统",
        "common_symptoms": ["头痛", "头晕", "肢体麻木", "无力", "言语不清", "抽搐", "睡眠障碍", "记忆下降"],
        "common_tests": ["神经系统查体", "头颅CT或MRI", "血压和血糖", "脑电图", "颈动脉超声", "凝血功能"],
        "urgent_signs": ["突发偏瘫", "口角歪斜", "言语困难", "雷击样头痛", "持续抽搐", "意识障碍"],
        "care": ["识别卒中预警症状", "控制血压血糖血脂", "规律作息", "康复训练", "遵医嘱使用抗栓或其他药物"],
        "departments": ["神经内科", "急诊科", "康复医学科"],
        "keywords": ["脑血管", "神经", "头痛", "眩晕", "癫痫"],
        "diseases": [
            "偏头痛", "紧张型头痛", "脑梗死", "短暂性脑缺血发作", "脑出血",
            "癫痫", "帕金森病", "阿尔茨海默病", "周围神经病变", "面神经炎",
            "良性阵发性位置性眩晕", "梅尼埃病", "失眠障碍", "颈椎病相关神经症状", "焦虑相关躯体症状",
        ],
    },
    {
        "name": "泌尿与肾脏",
        "common_symptoms": ["尿频", "尿急", "尿痛", "腰痛", "血尿", "泡沫尿", "水肿", "发热"],
        "common_tests": ["尿常规", "尿培养", "肾功能和电解质", "泌尿系超声", "尿蛋白定量", "前列腺相关检查"],
        "urgent_signs": ["高热寒战", "无尿或少尿", "肉眼血尿", "剧烈肾绞痛", "严重水肿", "血压显著升高"],
        "care": ["足量饮水", "避免憋尿", "控制血压血糖", "根据培养结果用药", "定期复查尿检和肾功能"],
        "departments": ["泌尿外科", "肾内科", "急诊科"],
        "keywords": ["尿路", "肾脏", "泌尿", "血尿", "蛋白尿"],
        "diseases": [
            "急性膀胱炎", "肾盂肾炎", "尿路结石", "慢性肾脏病", "急性肾损伤",
            "肾小球肾炎", "蛋白尿待查", "血尿待查", "前列腺增生", "前列腺炎",
            "尿失禁", "膀胱过度活动症", "高血压肾损害", "糖尿病肾病", "肾囊肿",
        ],
    },
    {
        "name": "骨科与风湿免疫",
        "common_symptoms": ["关节痛", "肌肉痛", "腰背痛", "晨僵", "肿胀", "活动受限", "麻木", "发热"],
        "common_tests": ["体格检查", "X线或MRI", "炎症指标", "风湿免疫抗体", "尿酸", "骨密度"],
        "urgent_signs": ["外伤后畸形", "下肢无力伴大小便异常", "关节红肿热痛伴高热", "突发不能负重"],
        "care": ["保护关节", "规范康复训练", "体重管理", "急性期适当休息", "遵医嘱抗炎镇痛或免疫治疗"],
        "departments": ["骨科", "风湿免疫科", "康复医学科"],
        "keywords": ["关节", "骨骼", "风湿", "疼痛", "康复"],
        "diseases": [
            "骨关节炎", "类风湿关节炎", "强直性脊柱炎", "痛风性关节炎", "腰椎间盘突出",
            "颈椎病", "肩周炎", "腱鞘炎", "骨质疏松性骨折风险", "系统性红斑狼疮",
            "干燥综合征", "肌筋膜疼痛综合征", "半月板损伤", "踝关节扭伤", "腕管综合征",
        ],
    },
    {
        "name": "皮肤与过敏",
        "common_symptoms": ["皮疹", "瘙痒", "红斑", "水疱", "脱屑", "风团", "色素改变", "疼痛"],
        "common_tests": ["皮肤视诊", "真菌镜检", "过敏原评估", "皮肤镜", "必要时皮肤活检", "血常规"],
        "urgent_signs": ["喉头水肿", "呼吸困难", "广泛水疱", "高热伴皮疹", "皮疹迅速扩散", "过敏性休克表现"],
        "care": ["避免诱因", "保持皮肤清洁保湿", "规范外用药", "避免搔抓", "严重过敏及时就医"],
        "departments": ["皮肤科", "变态反应科", "急诊科"],
        "keywords": ["皮肤", "过敏", "瘙痒", "皮疹", "炎症"],
        "diseases": [
            "湿疹", "荨麻疹", "接触性皮炎", "特应性皮炎", "银屑病",
            "痤疮", "脂溢性皮炎", "带状疱疹", "单纯疱疹", "体癣",
            "足癣", "甲真菌病", "玫瑰痤疮", "白癜风", "药疹风险评估",
        ],
    },
    {
        "name": "感染性疾病",
        "common_symptoms": ["发热", "寒战", "乏力", "肌痛", "局部红肿热痛", "咳嗽", "腹泻", "皮疹"],
        "common_tests": ["体温曲线", "血常规", "C反应蛋白或降钙素原", "病原学检测", "培养和药敏", "影像学检查"],
        "urgent_signs": ["高热不退", "意识改变", "血压下降", "呼吸急促", "皮肤花斑", "严重脱水"],
        "care": ["寻找感染灶", "合理使用抗菌药物", "隔离传染源", "补液和支持治疗", "监测病情变化"],
        "departments": ["感染科", "急诊科", "全科医学科"],
        "keywords": ["感染", "发热", "病原体", "抗菌药", "传染"],
        "diseases": [
            "发热待查", "细菌性感染", "病毒性感染", "脓毒症风险识别", "手足口病",
            "水痘", "麻疹风险评估", "流行性腮腺炎", "登革热风险评估", "狂犬病暴露后处置",
            "破伤风风险评估", "带状疱疹", "诺如病毒感染", "食源性疾病", "寄生虫感染风险评估",
        ],
    },
    {
        "name": "儿科",
        "common_symptoms": ["发热", "咳嗽", "腹泻", "呕吐", "皮疹", "哭闹", "食欲下降", "精神差"],
        "common_tests": ["体温和精神状态评估", "血常规", "尿常规", "便常规", "病原学检测", "生长发育评估"],
        "urgent_signs": ["精神萎靡", "呼吸困难", "惊厥", "持续高热", "脱水", "皮肤发花", "婴儿拒奶"],
        "care": ["按年龄评估病情", "补液和退热管理", "避免自行叠加用药", "观察尿量和精神状态", "及时复诊"],
        "departments": ["儿科", "儿童急诊", "儿童保健科"],
        "keywords": ["儿童", "发热", "生长发育", "疫苗", "儿科"],
        "diseases": [
            "儿童发热", "儿童急性上呼吸道感染", "儿童肺炎", "儿童哮喘", "毛细支气管炎",
            "儿童腹泻病", "轮状病毒感染", "手足口病", "幼儿急疹", "儿童过敏性鼻炎",
            "儿童湿疹", "儿童缺铁性贫血", "维生素D缺乏性佝偻病", "儿童肥胖", "儿童便秘",
        ],
    },
    {
        "name": "妇产科",
        "common_symptoms": ["腹痛", "异常阴道出血", "白带异常", "外阴瘙痒", "月经不规律", "痛经", "妊娠反应"],
        "common_tests": ["妇科检查", "尿或血HCG", "盆腔超声", "白带常规", "宫颈筛查", "性传播感染检测"],
        "urgent_signs": ["妊娠期腹痛出血", "剧烈下腹痛", "大量出血", "发热伴盆腔痛", "胎动明显减少"],
        "care": ["规范避孕和备孕咨询", "孕期定期产检", "注意外阴清洁", "避免自行阴道用药", "异常出血及时就医"],
        "departments": ["妇科", "产科", "生殖医学科", "急诊科"],
        "keywords": ["妇科", "妊娠", "月经", "盆腔", "宫颈"],
        "diseases": [
            "阴道炎", "外阴阴道假丝酵母菌病", "细菌性阴道病", "盆腔炎性疾病", "痛经",
            "异常子宫出血", "子宫肌瘤", "子宫内膜异位症", "卵巢囊肿", "多囊卵巢综合征",
            "围绝经期综合征", "早孕反应", "妊娠期糖尿病", "妊娠期高血压疾病", "宫颈癌筛查异常",
        ],
    },
    {
        "name": "眼耳鼻喉口腔",
        "common_symptoms": ["眼红", "眼痛", "视物模糊", "耳痛", "耳鸣", "鼻塞", "咽痛", "牙痛"],
        "common_tests": ["视力和眼压检查", "裂隙灯检查", "耳镜或鼻内镜", "听力检查", "口腔检查", "影像学检查"],
        "urgent_signs": ["突然视力下降", "眼外伤", "剧烈眼痛伴头痛", "吞咽或呼吸困难", "面部肿胀发热"],
        "care": ["避免揉眼", "保持口腔卫生", "规范使用滴眼液或耳鼻喉药物", "控制过敏诱因", "定期口腔检查"],
        "departments": ["眼科", "耳鼻喉科", "口腔科", "急诊科"],
        "keywords": ["眼科", "耳鼻喉", "口腔", "视力", "咽喉"],
        "diseases": [
            "急性结膜炎", "干眼症", "麦粒肿", "白内障", "青光眼风险识别",
            "中耳炎", "耳鸣", "突发性耳聋", "鼻窦炎", "过敏性鼻炎",
            "急性咽喉炎", "扁桃体炎", "口腔溃疡", "龋齿", "牙周炎",
        ],
    },
    {
        "name": "精神心理与睡眠",
        "common_symptoms": ["情绪低落", "兴趣减退", "焦虑", "心慌", "失眠", "注意力下降", "疲惫", "躯体不适"],
        "common_tests": ["心理量表筛查", "睡眠评估", "甲状腺功能等躯体病因排查", "药物和物质使用评估", "风险评估"],
        "urgent_signs": ["自伤自杀想法", "伤人风险", "幻觉妄想", "严重失眠伴行为失控", "意识混乱"],
        "care": ["规律作息", "心理治疗或咨询", "减少酒精和成瘾物质", "建立支持系统", "遵医嘱使用精神科药物"],
        "departments": ["精神心理科", "睡眠医学科", "全科医学科", "急诊科"],
        "keywords": ["心理", "睡眠", "焦虑", "抑郁", "压力"],
        "diseases": [
            "抑郁障碍", "广泛性焦虑障碍", "惊恐障碍", "失眠障碍", "躯体症状障碍",
            "强迫症", "创伤后应激障碍", "双相情感障碍风险识别", "注意缺陷多动障碍", "酒精使用障碍",
            "尼古丁依赖", "进食障碍风险识别", "产后抑郁风险", "老年认知障碍伴情绪问题", "职业倦怠相关心理问题",
        ],
    },
]


AGE_GROUPS = [
    ("儿童", "儿童患者需结合年龄、体重、精神反应和尿量评估，药物剂量应由医生按体重决定。"),
    ("青壮年", "青壮年患者常与工作压力、感染暴露、运动损伤和生活方式相关，需要关注病程变化。"),
    ("老年人", "老年患者常合并多种慢病，用药相互作用和不典型表现更常见，应降低就医阈值。"),
    ("孕产期", "孕产期患者需优先考虑母胎安全，任何用药和检查都应由妇产科或相关专科评估。"),
]


SCENARIOS = [
    ("初诊识别", "用于根据主诉和危险信号判断是否需要急诊或专科就诊。"),
    ("慢病随访", "用于追踪症状控制、生活方式、复查指标和药物依从性。"),
    ("检查解读", "用于把常见检查项目与可能疾病方向关联起来，但不能替代医生判读。"),
    ("用药教育", "用于说明常见治疗原则、注意事项和复诊条件，不提供个人化处方。"),
    ("康复管理", "用于提供恢复期观察、复查和生活方式管理要点。"),
    ("鉴别诊断", "用于比较相似症状背后的常见疾病，并强调需要临床检查确认。"),
]


SEVERITIES = [
    ("轻症", "症状较轻、生命体征稳定，通常先进行基础评估和对症处理。"),
    ("中等风险", "症状影响日常生活或持续进展，需要门诊进一步检查和随访。"),
    ("高风险", "存在并发症或危险信号可能，需要尽快到急诊或专科评估。"),
]


REGIONS = ["中国大陆城市社区", "县域基层医疗场景", "综合医院门诊", "急诊预检分诊", "家庭健康管理"]


QUESTION_PATTERNS = [
    "{age}出现{symptom}，可能和{disease}有关吗？",
    "{disease}常见表现有哪些，什么时候需要就医？",
    "{disease}需要做哪些检查来辅助判断？",
    "{disease}和哪些疾病容易混淆？",
    "{age}{disease}日常管理要注意什么？",
    "{scenario}场景下，{disease}应关注哪些风险？",
]


DIFFERENTIALS = [
    "感染性疾病", "过敏或免疫相关疾病", "肿瘤性疾病", "代谢异常", "药物不良反应",
    "功能性疾病", "外伤或劳损", "心脑血管急症", "精神心理因素", "妊娠相关问题",
]


SOURCE_NOTE = [
    "本语料参考现实医学知识体系的常见分类方式，组织方式借鉴了公开健康教育资源的通用表达。",
    "可用于核对的公开资料来源包括 MedlinePlus Health Topics、CDC Diseases & Conditions、WHO Fact Sheets、Merck Manual Consumer Version 等。",
    "语料面向医疗知识库、RAG评测和临床决策支持原型，不等同于临床指南、诊断标准或个体化诊疗建议。",
]


def pick(items: list[str], seed: int, count: int) -> list[str]:
    if not items:
        return []
    return [items[(seed + i) % len(items)] for i in range(count)]


def make_record(record_id: int, system: dict, disease: str, variant_index: int) -> str:
    age, age_note = AGE_GROUPS[(record_id + variant_index) % len(AGE_GROUPS)]
    scenario, scenario_note = SCENARIOS[(record_id // 3 + variant_index) % len(SCENARIOS)]
    severity, severity_note = SEVERITIES[(record_id // 7 + variant_index) % len(SEVERITIES)]
    region = REGIONS[(record_id // 11 + variant_index) % len(REGIONS)]
    symptoms = pick(system["common_symptoms"], record_id, 4)
    tests = pick(system["common_tests"], record_id // 2, 4)
    urgent = pick(system["urgent_signs"], record_id // 5, 3)
    care = pick(system["care"], record_id // 7, 4)
    departments = pick(system["departments"], record_id // 13, min(2, len(system["departments"])))
    keywords = list(dict.fromkeys([*system["keywords"], disease, age, scenario, severity]))
    question = QUESTION_PATTERNS[record_id % len(QUESTION_PATTERNS)].format(
        age=age,
        symptom=symptoms[0],
        disease=disease,
        scenario=scenario,
    )
    differential = pick(DIFFERENTIALS, record_id // 17, 4)

    return f"""### MED-{record_id:05d}｜{system["name"]}｜{disease}｜{scenario}

**适用人群**：{age}。{age_note}
**场景**：{region}；{scenario}。{scenario_note}
**风险分层**：{severity}。{severity_note}
**典型问题**：{question}

**疾病概念**
{disease}属于{system["name"]}常见健康问题之一。RAG回答时应先确认患者年龄、症状持续时间、基础疾病、妊娠状态、近期用药和是否出现危险信号，再给出通用健康教育和就医建议。

**常见表现**
常见线索包括：{"、".join(symptoms)}。不同患者表现可能不典型，老人、儿童、孕产期人群以及免疫功能低下者需要更谨慎评估。

**辅助检查**
可根据病情考虑：{"；".join(tests)}。检查选择应结合病史和体格检查，不能只凭单一指标下结论。

**鉴别方向**
需要与{"、".join(differential)}等情况区分。若症状进展快、反复发作或治疗反应差，应进一步评估。

**处理原则**
基础处理包括：{"；".join(care)}。具体药物、剂量和疗程必须由有资质的医生结合检查结果决定。

**危险信号**
出现{"、".join(urgent)}时，不建议继续在家观察，应尽快前往急诊或联系当地医疗服务。

**建议就诊科室**
优先考虑：{"、".join(departments)}。基层首诊后可按病情转诊到相应专科。

**RAG检索关键词**
{", ".join(keywords)}
"""


def allocate_records(total: int) -> list[tuple[dict, str, int]]:
    disease_pairs = []
    for system in SYSTEMS:
        for disease in system["diseases"]:
            disease_pairs.append((system, disease))

    allocation = []
    base = total // len(disease_pairs)
    remainder = total % len(disease_pairs)
    for i, (system, disease) in enumerate(disease_pairs):
        count = base + (1 if i < remainder else 0)
        allocation.extend((system, disease, v) for v in range(count))
    return allocation


def write_corpus(output: Path, total: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    allocation = allocate_records(total)
    lines = [
        "# 医疗常见病 RAG 测试语料库",
        "",
        f"生成日期：{date.today().isoformat()}",
        f"知识卡数量：{len(allocation)}",
        "",
        "## 重要声明",
        "",
        "- 本文件用于医疗知识库、RAG 检索、召回、重排序、问答生成和临床决策支持原型评测。",
        "- 内容按现实医学知识体系组织，覆盖常见病识别、检查思路、处理原则、危险信号和就医路径。",
        "- 本语料不替代执业医师诊断、处方、治疗方案或急救指导；真实患者应由具备资质的医疗人员评估。",
        "- 急危重症、疑似传染病暴发、妊娠相关异常、儿童重症风险和精神心理危机应立即进入线下医疗流程。",
        "",
        "## 参考体系说明",
        "",
        *[f"- {note}" for note in SOURCE_NOTE],
        "",
        "## 覆盖范围",
        "",
    ]
    for system in SYSTEMS:
        lines.append(f"- {system['name']}：{len(system['diseases'])} 个常见主题")
    lines.extend(["", "## 知识卡", ""])

    system_counter: Counter[str] = Counter()
    disease_counter: Counter[str] = Counter()
    for record_id, (system, disease, variant_index) in enumerate(allocation, start=1):
        system_counter[system["name"]] += 1
        disease_counter[disease] += 1
        lines.append(make_record(record_id, system, disease, variant_index))

    summary = [
        "",
        "## 统计摘要",
        "",
        f"- 总知识卡：{len(allocation)}",
        f"- 系统分类：{len(SYSTEMS)}",
        f"- 疾病主题：{len(disease_counter)}",
        "",
        "### 按系统统计",
        "",
    ]
    for name, count in system_counter.most_common():
        summary.append(f"- {name}：{count} 条")
    lines.extend(summary)

    output.write_text("\n".join(lines), encoding="utf-8")


def write_split_corpus(output_dir: Path, total: int, per_file: int) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    allocation = allocate_records(total)
    file_count = math.ceil(len(allocation) / per_file)
    written = []
    for file_index in range(file_count):
        chunk = allocation[file_index * per_file : (file_index + 1) * per_file]
        output = output_dir / f"medical_rag_corpus_part_{file_index + 1:02d}.md"
        lines = [
            f"# 医疗常见病 RAG 测试语料库 Part {file_index + 1:02d}",
            "",
            f"生成日期：{date.today().isoformat()}",
            f"本文件知识卡数量：{len(chunk)}",
            f"总文件数：{file_count}",
            "",
            "## 重要声明",
            "",
            "本文件用于医疗知识库、RAG评测和临床决策支持原型；不替代执业医师诊断、处方、治疗方案或急救指导。真实患者请咨询执业医师，急危重症请立即就医。",
            "",
            "## 知识卡",
            "",
        ]
        for offset, (system, disease, variant_index) in enumerate(chunk, start=file_index * per_file + 1):
            lines.append(make_record(offset, system, disease, variant_index))
        output.write_text("\n".join(lines), encoding="utf-8")
        written.append(output)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a Chinese medical RAG test corpus.")
    parser.add_argument("--total", type=int, default=10000, help="Number of knowledge cards to generate.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/rag_test_corpus/medical_rag_corpus_10000.md"),
        help="Single Markdown output path.",
    )
    parser.add_argument(
        "--split-dir",
        type=Path,
        default=Path("docs/rag_test_corpus/split"),
        help="Directory for split Markdown files.",
    )
    parser.add_argument(
        "--split-only",
        action="store_true",
        help="Only generate split Markdown files and skip the single large output.",
    )
    parser.add_argument("--per-file", type=int, default=1000, help="Knowledge cards per split file.")
    args = parser.parse_args()

    if args.total < 1:
        raise SystemExit("--total must be greater than zero")
    if args.per_file < 1:
        raise SystemExit("--per-file must be greater than zero")

    if not args.split_only:
        write_corpus(args.output, args.total)
    split_files = write_split_corpus(args.split_dir, args.total, args.per_file)
    if not args.split_only:
        print(f"Generated single corpus: {args.output} ({args.total} cards)")
    print(f"Generated {len(split_files)} split files in: {args.split_dir}")


if __name__ == "__main__":
    main()
