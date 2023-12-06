export const getCurrentPageContent = (router, container, breadcrumbContainer, title = '') => {
    const url = router.currentRoute.fullPath
    const stateKey = window.history.state && window.history.state.key
    const breadcrumbs = []

    const override = {
        [stateKey]: {
            breadcrumbs,
            url: url,
            urlName: container.getAttribute('data-url-name'),
            stateKey: stateKey,
            title,
            slots: {
                default: [...container.childNodes.values()],
            },
        },
    }

    if (breadcrumbContainer) {
        breadcrumbContainer.querySelectorAll('a, strong').forEach(n => {
            if (n.tagName === 'A') {
                breadcrumbs.push({ url: n.getAttribute('href'), text: n.textContent })
            } else breadcrumbs.push({ url: null, text: n.textContent })
        })
    }

    return override
}
