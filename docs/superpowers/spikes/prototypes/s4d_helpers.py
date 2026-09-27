def mat4_mul(a, b):  # column-major 4x4: a*b
    return [sum(a[k * 4 + r] * b[c * 4 + k] for k in range(4)) for c in range(4) for r in range(4)]


def worlds_by(s):
    """World matrices keyed by paint_objects-order names (mesh_datas)."""
    T = s["mesh_transforms"]
    P = s["mesh_parents"] or [-1] * len(T)
    names = s["mesh_data_names"]
    out = {}

    def w(i):
        if i not in out:
            out[i] = T[i] if P[i] < 0 else mat4_mul(w(P[i]), T[i])
        return out[i]
    return {names[i]: w(i) for i in range(len(names))}


def maxdiff(a, b):
    return max(abs(x - y) for x, y in zip(a, b))
