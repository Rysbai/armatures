import argparse
from collections import namedtuple
from decimal import Decimal
from functools import partial
import logging
import json
from typing import TextIO

_log = logging.getLogger()
_log.setLevel(logging.DEBUG)

ENTITY_TYPE = "  0"
Point = namedtuple("P", ("x", "y", "z"))
Line = namedtuple("LINE", ("a", "b"))
ThreeDFace = namedtuple("ThreeDFace", ("a", "b", "c", "d"))
LwPolyLine = namedtuple("LWPOLYLINE", ('points', ))


POINTS: set[Point] = set()


def point_factory(x: str, y: str, z: str) -> Point:
    # TODO
    POINTS.add(Point(x, y, z))


def parse_decimal(num: str) -> Decimal:
    return Decimal(num).quantize(Decimal(1000) ** -2)


def readlines(f: TextIO, nlines: int):
    lines = []
    for _ in range(nlines):
        line = f.readline()
        if line == "":
            break

        lines.append(line.strip())

    return lines


def read_code_value(f: TextIO, code: str, parser: callable = str) -> str:
    while True:
        line = f.readline()
        if line == "":  # end of file
            return "ENDOFFILE"

        if line == (code + '\n'):
            return parser(f.readline().strip())


def read_codes(f: TextIO, codes: list[str], parser: callable = str) -> list[str]:
    return [read_code_value(f, code, parser) for code in codes]


read_decimal = partial(read_code_value, parser=parse_decimal)
read_decimals = partial(read_codes, parser=parse_decimal)


def parse_LINE(f: TextIO) -> Line:
    a = Point(*read_decimals(f, [" 10", " 20", " 30"]))
    b = Point(*read_decimals(f, [" 11", " 21", " 31"]))
    return Line(a, b)


def parse_POINT(f: TextIO) -> Point:
    return Point(*read_decimals(f, [" 10", " 20", " 30"]))


def parse_3DFACE(f: TextIO) -> ThreeDFace:
    a = Point(*read_decimals(f, [" 10", " 20", " 30"]))
    b = Point(*read_decimals(f, [" 11", " 21", " 31"]))
    c = Point(*read_decimals(f, [" 12", " 22", " 32"]))
    d = Point(*read_decimals(f, [" 13", " 23", " 33"]))
    return ThreeDFace(a, b, c, d)


def parse_LWPOLYLINE(f: TextIO) -> LwPolyLine:
    points: set(Point) = set()
    n_verticies = read_code_value(f, " 90")

    for _ in range(int(n_verticies)):
        line = f.readline()
        if line == "":  # end of file
            break

        if line == '  0':  # end of the section or entity
            break

        x = parse_decimal(line.strip())
        y = read_decimal(f, ' 20')
        z = parse_decimal('0.00')

        points.add(Point(x, y, z))
    
    return LwPolyLine(points)


ENTITY_PARSERS = {
    "POINT": parse_POINT,
    "LINE": parse_LINE,
    "3DFACE": parse_3DFACE,
    "LWPOLYLINE": parse_LWPOLYLINE,
}


def parse_entities(f: TextIO):
    entities = []
    while True:
        entity_type = read_code_value(f, ENTITY_TYPE)
        if entity_type == "ENDSEC" or entity_type == "ENDOFFILE":
            return entities

        # NOTE: Entity Type should not be numeric
        # this migght happen if some entity type have not been handled
        if entity_type.isnumeric():
            continue

        entity_parser = ENTITY_PARSERS.get(entity_type)
        if entity_parser is None:
            _log.warning(f"Parser for {entity_type} not found on map")
            continue

        entities.append(entity_parser(f))


def main(filename: str):
    with open(f"test-files/{filename}") as f:
        while True:
            section = read_code_value(f, "  2")

            if section == "ENDOFFILE":  # end of file
                break

            if section == "ENTITIES":
                entities = parse_entities(f)
                print(json.dumps(_dump(entities), indent=2))
                break


def _dump(obj: namedtuple or list[namedtuple]) -> str:
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
    parser.add_argument("--filename", default="Drawing1.dxf", required=False)
    args = parser.parse_args()
    print("Parsing file: ", "test-files/" + args.filename)
    main(args.filename)
