export type PrimType = 'xform' | 'geom' | 'camera' | 'light' | 'scope' | string;

export type USDPrim = {
  name: string;
  path: string;
  type?: PrimType;
  hasChildren?: boolean;
  children?: USDPrim[] | null;
};

export type ServerPrim = Omit<USDPrim, 'children'> & {
  children?: boolean | ServerPrim[] | null;
  has_children?: boolean;
};

export type AssetItem = {
  id: string;
  name: string;
  path: string;
};

export function normalizePrim(prim: ServerPrim): USDPrim {
  const loadedChildren = Array.isArray(prim.children) ? prim.children.map(normalizePrim) : undefined;
  const hasChildren = Array.isArray(prim.children)
    ? prim.children.length > 0 || Boolean(prim.hasChildren ?? prim.has_children)
    : Boolean(prim.hasChildren ?? prim.has_children ?? prim.children);
  return {
    name: prim.name,
    path: prim.path,
    type: prim.type,
    hasChildren,
    children: loadedChildren ?? null,
  };
}

export function updatePrimChildren(prims: USDPrim[], targetPath: string, children: USDPrim[]): USDPrim[] {
  return prims.map((prim) => {
    if (prim.path === targetPath) return { ...prim, children, hasChildren: children.length > 0 || prim.hasChildren };
    if (prim.children) return { ...prim, children: updatePrimChildren(prim.children, targetPath, children) };
    return prim;
  });
}

