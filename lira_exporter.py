

def unique_points(face):
    points = []
    ids = set()
    for point in points:
        if point.id in ids:
            continue

        points.append(point)
        ids.add(point.id)

    return points


def _write_to_lira_file(f, layers, points):
    # HEADERS
    f.writelines([
        "(0/1;csv2lira/2;5/39; 1:'dead load';)(1/\n",
        "\n",
    ])

    # entities
    for layer in layers:
        lines = []
        for line in layer.lines:
            lines.append(f'5 {layer.id} {line.a.id} {line.b.id}/\n')
 
        for face in layer.faces:
            p_ids = " ".join([str(p.id) for p in face.points])
            if len(face.points) == 3:  # Triangle 3DFACE
                lines.append(f"42 {layer.id} {p_ids}/\n")
                continue

            lines.append(f"44 {layer.id} {p_ids}/\n")
 
        f.writelines(lines)
 
    # layers
    f.writelines(['\n', ')(3/\n'])
    lines = []
    for layer in layers:
        attrs = " ".join([str(at) for at in layer.attrs])
        line = f'{layer.id} S0 3.06E6 {attrs}/\n' # For LINE
        if len(layer.attrs) == 1:  # 3DFACE
            line = f'{layer.id} 3.06E6 0.2 {attrs}/\n'

        lines.append(line)

    f.writelines(lines)

    # Points
    f.writelines(['\n', ')(4/\n',])
    for point in points:
        f.writelines([f'{point.x} {point.y} {point.z}/\n'])

    # What is these?
    f.writelines([
        '\n',
        '\n',
        '\n)(6/1 16 3 1 1/)',
        '\n(7/1 0.0 0.0 0.0 0.0 /)',
        '\n(8/0 0 0 0 0 0 0/)',
        '\n',
    ])


def export_to_lira_csv(layers: list[tuple], points: list, filename: str):
    with open(filename + '__lira.txt', 'w') as f:
        _write_to_lira_file(f, layers, points)
