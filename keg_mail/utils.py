def dict_map(fn, dict_):
    return {key: fn(value) for key, value in dict_.items()}
