function readFile(file, asText = false) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(reader.result)
        reader.onerror = e => reject(e)
        if (asText) {
            reader.readAsText(file)
        } else {
            reader.readAsDataURL(file)
        }
    })
}

export { readFile }
