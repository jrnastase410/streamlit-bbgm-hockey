import msgspec


def load_json(json_file):
    file_content = json_file.read()
    return msgspec.json.decode(file_content)
