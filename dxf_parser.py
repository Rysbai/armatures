import argparse
import time
import re
from collections import namedtuple, OrderedDict
from decimal import Decimal
import logging
from typing import Any, Callable, TextIO

_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)


# 3 decimal digits
FLOAT_TOLLERENCE = 3
ENTITY_TYPE = "  0"
class Point(namedtuple("P", ("x", "y", "z", "id"), defaults=(None, ))):
    pass


class Layer(namedtuple("LAYER", ("name", "id", "attrs", "lines", "faces", "points", "lwpolines"))):
    pass


Line = namedtuple("LINE", ("a", "b"))
ThreeDFace = namedtuple("ThreeDFace", ('points'))
LwPolyLine = namedtuple("LWPOLYLINE", ('points', ))


POINTS: dict[tuple[str, str, str], Point] = OrderedDict()
SEQUENCES = {}

def _counter(sequence_id: str, start = 1, step = 1):
    SEQUENCES[sequence_id] = start

    while True:
        yield SEQUENCES[sequence_id]
        SEQUENCES[sequence_id] = SEQUENCES[sequence_id] + step


POINT_ID_SEQUENCE = _counter('points')
LAYER_ID_SEQUENCE = _counter('layers')


def strip_tollerence(num: str) -> str:
    f = num.split('.')
    if len(f) == 2:
        return f[0] + "." + f[1][:FLOAT_TOLLERENCE]

    return num


def point_factory(x: str, y: str, z: str) -> Point:
    hash_ = (
        strip_tollerence(x),
        strip_tollerence(y),
        strip_tollerence(z),
    )

    if hash_ in POINTS:
        return POINTS[hash_]

    p = Point(float(x), float(y), float(z), next(POINT_ID_SEQUENCE))
    POINTS[hash_] = p 
    return p


def read_code_value(f: TextIO, code: str, parser: Callable = str) -> str:
    while True:
        line = f.readline()
        if line == "":  # end of file
            return "ENDOFFILE"

        if line == (code + '\n'):
            return parser(f.readline().strip())


def read_codes(f: TextIO, codes: list[str], parser: Callable = str) -> list[str]:
    return [read_code_value(f, code, parser) for code in codes]


def parse_LINE(f: TextIO) -> Line:
    a = point_factory(*read_codes(f, [" 10", " 20", " 30"]))
    b = point_factory(*read_codes(f, [" 11", " 21", " 31"]))
    return Line(a, b)


def parse_POINT(f: TextIO) -> Point:
    return point_factory(*read_codes(f, [" 10", " 20", " 30"]))


def unique_points(*points):
    _points = []
    ids = set()
    for point in points:
        if point.id in ids:
            continue

        _points.append(point)
        ids.add(point.id)

    return tuple(_points)


def parse_3DFACE(f: TextIO) -> ThreeDFace:
    a = point_factory(*read_codes(f, [" 10", " 20", " 30"]))
    b = point_factory(*read_codes(f, [" 11", " 21", " 31"]))
    c = point_factory(*read_codes(f, [" 12", " 22", " 32"]))
    d = point_factory(*read_codes(f, [" 13", " 23", " 33"]))
    return ThreeDFace(unique_points(a, b, d, c))


def parse_LWPOLYLINE(f: TextIO) -> LwPolyLine:
    points: set[Point] = set()
    n_verticies = read_code_value(f, " 90")

    for _ in range(int(n_verticies)):
        line = f.readline()
        if line == "":  # end of file
            break

        if line == '  0':  # end of the section or entity
            break

        x = line.strip()
        y = read_code_value(f, ' 20')
        z = '0.00'

        points.add(Point(x, y, z))
    
    return LwPolyLine(points)


ENTITY_PARSERS = {
    "POINT": parse_POINT,
    "LINE": parse_LINE,
    "3DFACE": parse_3DFACE,
    "LWPOLYLINE": parse_LWPOLYLINE,
}

ENTITY_MAPS = {
    "POINT": "points",
    "LINE": "lines",
    "3DFACE": "faces",
    "LWPOLYLINE": "lwpolylines",

    # TODO: Три угольный 3DFACE, лира код 42 <названия слоя> <и три координаты>
}


def parse_layer_name(entity_type: str, layer_name: str) -> list[str]:
    b_pattern = r'B\d+'
    h_pattern = r'H\d+'

    if entity_type == 'LINE':
        b_val = re.findall(b_pattern, layer_name)
        h_val = re.findall(h_pattern, layer_name)

        if not (b_val and h_val):
            return []

        return [float(b_val[0][1:]), float(h_val[0][1:])]

    if entity_type == '3DFACE':
        h_val = re.findall(h_pattern, layer_name)
        if not h_val:
            return []

        return [float(h_val[0][1:]) / 100]


def parse_entities(f: TextIO):
    layers = {}

    while True:
        entity_type = read_code_value(f, ENTITY_TYPE)
        if entity_type == "ENDSEC" or entity_type == "ENDOFFILE":
            break

        # NOTE: Entity Type should not be numeric
        # this migght happen if some entity type have not been handled
        if entity_type.isnumeric():
            continue

        entity_parser = ENTITY_PARSERS.get(entity_type)
        if entity_parser is None:
            _log.warning(f"Parser for {entity_type} not found")
            continue

        layer_name = read_code_value(f, '  8')
        attrs = parse_layer_name(entity_type, layer_name)
        if not attrs:  # Invalid layer name
            continue
    
        layer = layers.get(layer_name)
        if not layer:
            layer = Layer(layer_name, next(LAYER_ID_SEQUENCE), attrs, [], [], [], [])
            layers[layer_name] = layer

        entity = entity_parser(f)
        getattr(layer, ENTITY_MAPS[entity_type]).append(entity)

    return list(layers.values())


def parse_dxf(filename: str):
    start = time.time()
    layers = []
    result_fname, _ = filename.split('.')
    with open(filename) as f:
        while True:
            section = read_code_value(f, "  2")

            if section == "ENDOFFILE":  # end of file
                break

            if section == "ENTITIES":
                layers = parse_entities(f)

    end = time.time()
    _log.warning(f'Finished parsing in: {end - start}s')

    from lira_exporter import export_to_lira_csv
    export_to_lira_csv(layers, POINTS.values(), result_fname)

    # with open(result_fname + '_result.json', 'w') as f:
    #     result = _dump(layers)
    #     json.dump(result, f)

    end = time.time()
    _log.warning(f'Finished writing results in: {end - start}s')

    return layers


def _dump(obj: tuple | list[tuple]) -> Any:
    if isinstance(obj, tuple) and hasattr(obj, '_asdict'):
        return {
            obj.__class__.__name__: {k: _dump(v) for k, v in obj._asdict().items()}
        }

    if isinstance(obj, (list, set)):
        return [_dump(el) for el in obj]

    if isinstance(obj, Decimal):
        return str(obj)
 
    return obj


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--filename", default="test-files/Drawing1.dxf", required=False)
    args = parser.parse_args()
    _log.warning(f"Parsing file: {args.filename}", )
    parse_dxf(args.filename)
