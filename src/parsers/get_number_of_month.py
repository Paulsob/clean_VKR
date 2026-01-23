def get_month_number(month_name: str) -> int:
    months = [
        "Январь",
        "Февраль",
        "Март",
        "Апрель",
        "Май",
        "Июнь",
        "Июль",
        "Август",
        "Сентябрь",
        "Октябрь",
        "Ноябрь",
        "Декабрь"
    ]
    if month_name in months:
        return months.index(month_name) + 1
    else:
        raise ValueError(f"Unknown month: {month_name}")
