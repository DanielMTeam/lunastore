from constance import config


def get_motd_list() -> list[str]:
    # parse
    raw: str = config.MOTD_LIST
    return [m.strip() for m in raw.split(";") if m.strip()]
