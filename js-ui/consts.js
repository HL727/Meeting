const debug = process.env.NODE_ENV !== 'production'
const isTest = process.env.NODE_ENV === 'test'

const baseURL = process.env.VUE_APP_API_BASE ? process.env.VUE_APP_API_BASE : '/json-api/v1/'

const itemListSearchPrefix = '__MATCH_ALL__'

export { debug, baseURL, itemListSearchPrefix, isTest }
