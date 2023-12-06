import {
    format,
    parseISO,
    formatDistanceToNowStrict,
    formatDistance,
    sub,
    differenceInSeconds
} from 'date-fns'
import { enGB, sv } from 'date-fns/locale'

/* ************************* */
/* End user/interface helpers */
/* ************************* */

/**
 * End user friendly, full date + time
 */
export function timestamp(s) {
    if (!s) return ''

    const obj = s.getHours ? s : parseISO(s)
    return format(obj, 'yyyy-MM-dd HH:mm:ss', getDateOptions())
}

/**
 * End user friendly, how long ago a timestamp happened
 */
export function since(s) {
    if (!s) return ''

    return formatDistanceToNowStrict(parse(s), getDateOptions())
}

/**
 * End user friendly, how many days, etc. from seconds
 */
export function secondDuration(s) {
    return formatDistance(0, s * 1000, { includeSeconds: true, ...getDateOptions() })
}

/**
 * End user friendly, how many days, hours, seconds between now|tsStop
 */
export function duration(tsStart, tsEnd=null) {
    if (!tsStart) return ''

    const tsRealStart = typeof tsStart == 'number' ? new Date(new Date() - tsStart * 1000) : parse(tsStart)
    const tsRealEnd = tsEnd ? parse(tsEnd) : new Date()

    const diffSecs = differenceInSeconds(tsRealEnd, tsRealStart)
    const diffObj = new Date(diffSecs * 1000)

    const result = []
    if (diffSecs > 60 * 60 * 24) {
        result.push(Math.floor(diffSecs / (60 * 60 * 24)) + 'd')
    }
    if (diffSecs > 60 * 60) {
        // Format back to UTC for hours to be correct
        result.push(formatISO(diffObj).replace(/Z$/, '').replace(/.*T(00:)?/, ''))
    } else {
        result.push(formatDate(diffObj, 'mm:ss'))
    }

    return result.join(' ')
}

/* ********************* */
/*  now-based shortcuts  */
/* ********************* */

/**
 * Format UTC Iso timestamp without microseconds. Usable as API parameter
 */
export function formatISO(s) {
    if (!s) return ''
    return parse(s).toISOString().replace(/\.\d+Z/, 'Z')
}

/**
 * UTC timestamp, usable as API parameter
 */
export function now() {
    return formatISO(new Date())
}

/**
 * UTC timestamp, usable as API parameter
 */
export function nowSub(back) {
    return formatISO(sub(new Date(), back))
}

/**
 * Current full date + time in local timezone (without timezone info). Usable for old django forms
 */
export function localtime() {
    return formatLocalTimestamp(new Date())
}

/**
 * Shortcut for current full date + time in local timezone which subtracts parameter value, e.g. {hours: 1}
 */
export function localtimeSub(back) {
    return formatLocalTimestamp(sub(new Date(), back))
}


/* ******************** */
/*  format and parsing  */
/* ******************** */

/**
 * Parse text or return existing date object
 */
function parse(s) {
    return s && s.getHours ? s : parseISO(s)
}

/**
 * Format full date + time in local timezone (without timezone info). Usable for old django forms
 */
export function formatLocalTimestamp(s) {
    if (!s) return ''
    return formatDate(parse(s), 'yyyy-MM-dd HH:mm:ss')
}

/**
 * Format date object in current locale
 */
export function formatDate(date, dateFormat) {
    return format(parse(date), dateFormat, getDateOptions())
}

/**
 * Format date object as iso date
 */
export function isoDate(date) {
    return formatDate(date, 'yyyy-MM-dd')
}

/**
 * Split date string into date, time and date object
 */
export function parseDateString(value) {
    const dateObj = parse(value)

    return {
        date: format(dateObj, 'yyyy-MM-dd'),
        time: format(dateObj, 'HH:mm:ss'),
        obj: dateObj,
    }
}

/* ********** */
/*  settings  */
/* ********** */

/**
 * Global date options for date-fns
 */
function getDateOptions() {
    const lang = (window.MIVIDAS && window.MIVIDAS.language)
    const locales = {
        sv: sv,
        en: enGB,
    }

    return {
        locale: locales[lang || 'sv'],
    }
}
