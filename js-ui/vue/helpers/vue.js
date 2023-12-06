const camelizeRE = /-(\w)/g

export function camelize(str) {
    return str.replace(camelizeRE, (_, c) => c ? c.toUpperCase() : '')
}

export function normalizeProps(obj) {
    const result = {}
    let changed = false
    Object.keys(obj).forEach(k => {
        const camelized = camelize(k)
        result[camelized] = obj[k]
        if (camelized !== k) {
            changed = true
        }
    })
    return (changed) ? result : obj
}

export function mergeAttrs(...objs) {
    if (objs.length === 1) {
        return normalizeProps(objs[0])
    }
    const result = {}
    objs.forEach(o => {
        Object.assign(result, normalizeProps(o))
    })
    return result
}

export function defaultFilter(value, search) {
    return value != null &&
        search != null &&
        typeof value !== 'boolean' &&
        value.toString().toLocaleLowerCase().indexOf(search.toLocaleLowerCase()) !== -1
}
