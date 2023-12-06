let fn = null

export function $gettext(s) {
    if (!fn && window.MIVIDAS && window.MIVIDAS.$gettext) {
        fn = window.MIVIDAS.$gettext
    }
    return fn ? fn(s) : (window.gettext ? window.gettext(s) : s)
}
