"""
序列识别器：根据JD标题，自动识别使用哪个模板序列
序列：产品 / 研发 / 运营 / 商务 / 职能
"""
import json
import os

L3_TO_TEMPLATE = {
    "产品": "product_manager",
    "研发": "rd_engineer",
    "运营": "ops_manager",
    "商务": "sales_director",
    "职能": "hr_director",
}

# 通用词缀（太常见，会造成误匹配）
_GENERIC_SUFFIXES = {"经理", "总监", "工程师", "专员", "助理", "主管", 
                     "负责人", "总裁", "VP", "首席", "部长", "组长", "主任"}

# 直接映射：常见词 → L3序列（人工验证过）
_DIRECT_TERMS = {
    # 研发
    "前端": "研发", "后端": "研发", "算法": "研发", "数据": "研发",
    "客户端": "研发", "服务端": "研发", "测试": "研发", "运维": "研发",
    "嵌入式": "研发", "架构师": "研发", "芯片": "研发", "IC": "研发",
    "工艺": "研发", "电气": "研发", "机械": "研发", "结构": "研发",
    "客户端开发": "研发", "服务端开发": "研发", "无线": "研发",
    # 产品
    "产品经理": "产品", "产品": "产品", "项目经理": "产品",
    "制作人": "产品", "游戏制作人": "产品",
    # 运营
    "运营": "运营", "客服": "运营", "供应链": "运营", "采购": "运营",
    "物流": "运营", "仓储": "运营", "生产管理": "运营", "质量管理": "运营",
    "电商运营": "运营", "用户运营": "运营", "内容运营": "运营",
    # 商务
    "销售": "商务", "BD": "商务", "商务": "商务", "渠道": "商务",
    "市场": "商务", "品牌": "商务", "公关": "商务", "投放": "商务",
    "招商": "商务", "大客户": "商务", "经销商": "商务", "代理": "商务",
    # 职能
    "人力": "职能", "人力资源": "职能", "招聘": "职能", "培训": "职能",
    "薪酬": "职能", "绩效": "职能", "HR": "职能", "行政": "职能",
    "财务": "职能", "会计": "职能", "审计": "职能", "法务": "职能",
    "合规": "职能", "政府事务": "职能", "HRBP": "职能",
}

_L4_L5_MAP = None  # 按需加载


def _load_tree():
    global _L4_L5_MAP
    if _L4_L5_MAP is not None:
        return _L4_L5_MAP
    
    data_path = os.path.join(os.path.dirname(__file__), "..", "data", "industry_position_tree.json")
    try:
        tree = json.load(open(data_path, encoding="utf-8"))
    except Exception:
        tree = {}
    
    l4_l5_map = {}
    for ind_name, rows in tree.items():
        for row in rows:
            if row[0] == "L1-行业" or len(row) < 4:
                continue
            l3 = row[2].strip()
            if not l3:
                continue
            for field in [row[3], row[4] if len(row) > 4 else ""]:
                if not field:
                    continue
                for term in field.split("/"):
                    t = term.strip()
                    if t and t not in _GENERIC_SUFFIXES and len(t) >= 2 and t not in _DIRECT_TERMS:
                        if t not in l4_l5_map:
                            l4_l5_map[t] = l3
    _L4_L5_MAP = l4_l5_map
    return l4_l5_map


def identify_sequence(jd_title: str) -> str:
    """
    根据JD标题文本，识别使用哪个模板序列。
    返回：product_manager | rd_engineer | ops_manager | sales_director | hr_director
    """
    if not jd_title:
        return "product_manager"
    
    title = jd_title.strip()
    
    # 1. 直接匹配（优先级最高）
    for term, l3 in _DIRECT_TERMS.items():
        if term in title:
            return L3_TO_TEMPLATE[l3]
    
    # 2. 从行业树L4/L5关键词匹配
    l4_l5 = _load_tree()
    for term, l3 in l4_l5.items():
        if term in title:
            return L3_TO_TEMPLATE[l3]
    
    # 3. fallback: 通用产品
    return "product_manager"
