const path = require('path')

module.exports = {
    entry: {
        bundle: './main.js',
    },
    output: {
        filename: '[name].js',
        path: path.resolve(__dirname, '../../static/distv2'),
        publicPath: '/site_media/static/distv2/',
    },
    resolve: {
        extensions: ['.js', '.json', '.jsx'],
        alias: {
            '@': path.resolve(__dirname),
        },
    },
    devtool: process.env.NODE_ENV !== 'production' ? '#eval-source-map' : 'source-map',

    module: {
        rules: [
            {
                test: /react.*\.jsx$/,
                exclude: /(node_modules|bower_components)/,
                use: {
                    loader: 'babel-loader',
                    options: {
                        presets: ['babel-preset-env'],
                        plugins: ['transform-object-rest-spread', 'transform-react-jsx'],
                    },
                },
            },
            {
                test: /\.js$/,
                exclude: /(node_modules|bower_components)/,
                use: {
                    loader: 'babel-loader',
                    options: {
                        presets: ['babel-preset-env'],
                        plugins: ['transform-object-rest-spread'],
                    },
                },
            },
            {
                test: /\.(woff(2)?|ttf|eot|svg)(\?v=\d+\.\d+\.\d+)?$/,
                use: [
                    {
                        loader: 'file-loader',
                        options: {
                            name: '[name].[ext]',
                            outputPath: 'fonts/',
                        },
                    },
                ],
            },
            {
                test: /\.css$/,
                use: ['style-loader', 'css-loader'],
            },
            {
                test: /\.s(c|a)ss$/,
                use: [
                    'css-loader',
                    {
                        loader: 'sass-loader',
                        options: {
                            implementation: require('sass'),
                            fiber: require('fibers'),
                        },
                    },
                ],
            },
        ],
    },
    externals: {
        jquery: 'jQuery',
    },
}
