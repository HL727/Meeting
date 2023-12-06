const path = require('path')

module.exports = {
    filenameHashing: true,
    publicPath: process.env.NODE_ENV === 'production' ? '/site_media/static/dist/' : `http://${process.env.VUE_APP_SERVER_IP || 'localhost'}:8083/`,
    outputDir: 'static/dist/',
    devServer: {
        //contentBase: './static/dist',
        headers: { 'Access-Control-Allow-Origin': '*' },
        port: 8083,
        hot: true,
    },
    css: {
        //sourceMap: true,
    },
    lintOnSave: process.env.NODE_ENV !== 'production',
    transpileDependencies: ['vuetify'],
    chainWebpack: config => {

        const sourceDir = 'js-ui'
        const entry = config.entry('app')
        entry.clear() // Remove existing entry rule
        entry.add(`./${sourceDir}/main.js`)

        const alias = config.resolve.alias
        alias.set('@', path.resolve(sourceDir))

        config.externals({
            jquery: 'jQuery'
        })
    }
}
