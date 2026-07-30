def gate(args):
    x, y = int(args[0]), int(args[1])
    return [
        f'type_wall {1+x} {0+y} 8',
        f'type_wall {1+x} {2+y}',
        f'type_wall {2+x} {3+y} 7',
        f'type_wall {2+x} {2+y}',
        f'type_wall {2+x} {1+y} 9',
        f'type_wall {0+x} {1+y} 2',
        f'type_wall {0+x} {3+y}',
        f'type_wall {1+x} {4+y}'
        
    ]
