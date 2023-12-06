export const getFullTree = (id, items, key = 'id') => {
    const result = []

    const recurse = item => {
        if (item[key] == id) {
            result.push(item)
            return true
        }
        for (let child of item.children || []) {
            if (recurse(child)) {
                result.push(item)
                return true
            }
        }
    }

    recurse({ children: items })
    return result.reverse().slice(1)
}

export const filterNodes = (filter, nodes) => {
    return !filter
        ? nodes
        : nodes.filter(
            node =>
                JSON.stringify(node)
                    .toLowerCase()
                    .indexOf(filter.toLowerCase()) != -1
        )
}
export const filterNodesSorting = (a, b) => {
    if (a.depth === 0 && a.childrenGroupNodes.length === 0) {
        if (a.childrenGroupNodes.length < b.childrenGroupNodes.length) {
            return -1
        }
    }

    if (a.title > b.title) {
        return 1
    }
    if (a.title < b.title) {
        return -1
    }

    return 0
}

export const textPath = (id, items, text = 'title', key = 'id', separator=' / ') => {
    return getFullTree(id, items, key)
        .map(i => i[text])
        .join(separator)
}

export const mapTextPath = (id, items, text = 'title') => {
    const result = []

    let cur = id
    while (items[cur]) {
        result.push(items[cur][text])
        if (!(cur = items[cur].parent)) {
            break
        }
    }
    return result.reverse().join(' / ')
}

export const buildTree = items => {
    const recurse = parent => {
        return items
            .filter(i => i.parent == parent)
            .map(i => {
                const children = recurse(i.id)
                return {
                    ...i,
                    children,
                    totalNodes: children.reduce((acc, child) => acc + child.totalNodes, 1),
                }
            })
    }

    return recurse(null)
}

/** Create a new tree with each parent duplicated as a subnode to allow for tree views-selection */
export const duplicateParentsAsSubNodes = (tree, setItemTitleCallback, itemKey='id', requireCount=false) => {
    const recurse = item => {

        let children = (item.children || []).map(recurse)

        if (!children.length || (requireCount && !item.selfCount)) return { ...item, children }

        const childDuplicate = {
            ...item,
            isParentDuplicate: true,
            children: [],
            ...setItemTitleCallback(item),
            totalCount: item.selfCount || 0
        }
        children = [childDuplicate, ...children]

        // this is not used by tree-view when selection=leaf. If this conflicts with another id,
        // totalCounts in countItems must be filtered on isParentDuplicate
        const newId = 'fake' + (item[itemKey] || '').toString()

        return {
            ...item,
            [itemKey]: newId,
            duplicatedRealId: item[itemKey],
            children: children,
        }
    }

    return tree.map(recurse)
}

export const countItems = (tree, items, key = null, hideEmpty = false) => {
    const ids = !key ? items : items.map(i => i[key])

    const recurse = item => {
        const selfCount = ids.filter(id => item.id == id).length

        const children = item.children ? item.children.map(recurse) : []

        return {
            ...item,
            children: hideEmpty ? children.filter(c => c.totalCount) : children,
            selfCount,
            totalCount: children.reduce((acc, child) => acc + child.totalCount, selfCount),
            totalNodes: children.reduce((acc, child) => acc + child.totalNodes, 1),
        }
    }

    const counted = tree.map(recurse)
    return hideEmpty ? counted.filter(c => c.totalCount) : counted
}
