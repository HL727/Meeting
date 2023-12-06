export function idMap(lst, key = 'id') {
    const result = {}
    lst.forEach(item => (result[item[key]] = item))
    return result
}

export function groupList(lst, key) {
    const result = {}
    lst.forEach(item => {
        if (!result[item[key]]) result[item[key]] = []
        result[item[key]].push(item)
    })
    return result
}

export function filterList(lst, key, values) {
    return lst.filter(item => values.indexOf(item[key]) !== -1)
}

export function replaceObject(list, newObj) {
    let found = false
    const result = list.map(item => (item.id == newObj.id ? (found = newObj) : item))
    if (!found) result.push(newObj)
    return result
}

export function removeObject(list, id) {
    let found = false
    const result = (list || []).filter(i => i.id === id && (found = i))
    return found ? result : list || []
}


const _loading = {}

export async function singleGet(options, url) {
    if (!_loading[url]) {
        _loading[url] = this.api()
            .get(url)
            .catch(e => {
                setTimeout(() => {
                    _loading[url] = null
                }, 300)
                throw e
            })
            .then(r => {
                setTimeout(() => {
                    _loading[url] = null
                }, 300)
                return r
            })
    }
    // return copy so that result is not overriden by chained then()
    return new Promise((resolve, reject) =>
        _loading[url]
            .then(r => {
                resolve(r)
                return r
            })
            .catch(e => {
                reject(e)
            })
    )
}
