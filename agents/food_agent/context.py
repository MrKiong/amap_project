USER_PROFILE = {
    "home_area": "北京市朝阳区国典华园附近",
    "work_area": "北京市百子湾地铁站",
    "default_city": "北京",
    "default_party": {
        "people_count": 2,
        "relationship": "夫妻",
        "applies_when": "用户未指明其他用餐人数或社交场景时",
    },
    "preference_scope": {
        "primary_scope": "家庭/夫妻用餐偏好",
        "notes": [
            "本画像中的预算、菜系和口味偏好默认用于家庭或夫妻用餐场景",
            "如果用户说明是同事、商务、朋友、多人聚餐或其他非家庭场景，不要机械套用家庭偏好，应根据该场景独立判断",
        ],
    },
    "dining_scenarios": [
        {
            "name": "小吃一顿",
            "budget_per_person": "约30元",
            "description": "人均30左右的简餐，替代一顿普通午餐或晚餐，重点是方便、稳定、效率高。",
        },
        {
            "name": "吃点好的",
            "budget_per_person": "约80元",
            "description": "人均80左右的中等餐厅，适合临时改善一餐，但不需要很正式。",
        },
        {
            "name": "大吃一顿",
            "budget_per_person": "约120-300元",
            "description": "人均120-300左右的高等餐厅，更重视体验、品质和满足感。",
        },
    ],
    "budget_notes": [
        "通常不会选择超过人均400元的餐厅，除非用户特别说明",
    ],
    "cuisine_preferences": {
        "generally_accept": [
            "烤肉",
            "烤串",
            "烧烤",
            "日料",
            "中餐",
            "简餐",
            "各类中餐菜系",
        ],
        "reduce_recommendation": [
            "火锅",
        ],
        "brand_likes": [
            "麦当劳",
        ],
    },
    "preference_notes": [
        "希望推荐不要只看大众热门，而要结合个人偏好",
        "不喜欢过度排队",
        "更看重实际体验和复吃价值",
        "很少吃火锅，但不是完全不能吃；除非理由充分，否则减少推荐火锅",
        "爱吃麦当劳，小吃一顿或求稳场景下可以把它视为可接受选项",
    ],
}
