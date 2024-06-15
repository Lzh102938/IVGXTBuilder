import struct
import codecs
from array import array
from collections import namedtuple
from pathlib import Path

# 将一个字符串转换成8字节串
def str_to_8bytes(string: str):
    arr = array('B')
    bstring = string.encode('utf-8')
    if len(bstring) == 0 or len(bstring) > 7:
        raise ValueError

    arr.extend(bstring)
    while len(arr) < 8:
        arr.append(0)

    return bytes(arr)

def load_txt(file_path):
    tables = {}
    current_table = 'MAIN'
    tables[current_table] = []

    double_byte_chars = set()

    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    for line in lines:
        line = line.strip()
        if line.startswith('[') and line.endswith(']'):
            current_table = line[1:-1]  # 保留表名的大小写
            if current_table not in tables:
                tables[current_table] = []
        elif '=' in line:
            key, value = line.split('=', 1)
            hash_value = int(key, 16)  # 读取TXT文件中的哈希值
            tables[current_table].append({'original': key, 'translated': value.strip(), 'hash': hash_value})
            # Extract double-byte characters
            double_byte_chars.update([c for c in value.strip() if ord(c) > 255])

    return tables, double_byte_chars

def add_bom(utf8_path, bom: bytes):
    with open(utf8_path, 'r+b') as f:
        org_contents = f.read()
        f.seek(0)
        f.write(bom + org_contents)

def write_charset(chars, filename):
    char_per_line = 64
    char_index = 0
    chars = sorted(chars)
    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    with open(filename, "w", encoding='utf-8') as f:
        for char in chars:
            f.write(char)
            char_index += 1
            if char_index >= char_per_line:
                f.write('\n')
                char_index = 0
    add_bom(filename, codecs.BOM_UTF8)

def write_gxt(tables, filename):
    TableEntry = namedtuple("TableEntry", "name offset")
    KeyEntry = namedtuple("KeyEntry", "offset hash")
    Path(filename).parent.mkdir(parents=True, exist_ok=True)

    with open(filename, "wb") as f:
        f.write(b'\x04\x00\x10\x00')
        f.write(b'TABL')
        f.write(struct.pack('<I', len(tables) * 12))

        # 预留table data的空隙，先写入TKEY & TDAT并计算出Table的Offset值，再一次性写入TablBlock
        tkey_block_offset = 12 + len(tables) * 12
        f.seek(tkey_block_offset)

        # 排序表名，首先写入'MAIN'table
        sorted_keys = ['MAIN'] + [table_name for table_name in tables.keys() if table_name != 'MAIN']
        table_entries = list()

        for table_name in sorted_keys:
            # 生成Table Entry
            table_entries.append(TableEntry(str_to_8bytes(table_name), f.tell()))

            # 写入key block
            f.write(b'TKEY')
            f.write(struct.pack('<I', len(tables[table_name]) * 8))

            data_bytes = array('H')
            data_offset = 0

            for entry in tables[table_name]:
                f.write(struct.pack('<II', data_offset, entry['hash']))

                str_to_serialize = entry['translated'] if entry['translated'] else entry['original']
                data_bytes.extend([ord(c) for c in str_to_serialize])
                data_bytes.append(0)
                data_offset += len(str_to_serialize) * 2 + 2

            # 写入data block
            f.write(b'TDAT')
            f.write(struct.pack('<I', len(data_bytes) * 2))
            f.write(data_bytes.tobytes())

        # 最后写入TableBlock
        f.seek(12)
        table_block_bytes = array('B')

        for table_entry in table_entries:
            table_block_bytes.extend(struct.pack("<8sI", table_entry.name, table_entry.offset))

        f.write(table_block_bytes)

# 示例使用
input_txt_file = 'gta4.txt'
output_gxt_file = 'chinese.gxt'
charset_file = 'CHARACTERS.txt'

tables, double_byte_chars = load_txt(input_txt_file)
write_gxt(tables, output_gxt_file)
write_charset(double_byte_chars, charset_file)
