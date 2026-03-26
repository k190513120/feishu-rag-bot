def build_auth_card(oauth_url: str) -> dict:
    """Build the '访问凭证授权' interactive card. Button opens OAuth URL."""
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "\ud83d\udd10 访问凭证授权"},
            "template": "purple",
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        "点击下方按钮允许我获取您的访问凭证。"
                        "点击授权后，机器人将以您的访问凭证（access_token）"
                        "查询群id、是否外部群等群基础信息。"
                    ),
                },
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "授权"},
                        "type": "primary",
                        "url": oauth_url,
                    }
                ],
            },
        ],
    }


def build_user_identity_auth_card(oauth_url: str) -> dict:
    """Build card prompting user to authorize user-identity message sending."""
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "🔐 用户身份授权"},
            "template": "blue",
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        "我需要您的授权才能以用户身份发送消息。\n"
                        "请点击下方按钮完成授权，授权后请重新发送您的问题。"
                    ),
                },
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "立即授权"},
                        "type": "primary",
                        "url": oauth_url,
                    }
                ],
            },
        ],
    }


def build_confirm_card(chat_id: str) -> dict:
    """Build the '机器人入群确认' interactive card."""
    return {
        "header": {
            "title": {"tag": "plain_text", "content": "\ud83e\udd16 机器人入群确认"},
            "template": "purple",
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "点击下方按钮确认将机器人拉入群聊。",
                },
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "确认"},
                        "type": "primary",
                        "value": {
                            "action": "confirm_join_group",
                            "chat_id": chat_id,
                        },
                    }
                ],
            },
        ],
    }
