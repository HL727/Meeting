<template>
    <span><a
              v-translate
              href="#"
              @click.prevent="use"
          >Nästa löpnummer</a> <i>{{ number }}</i>
        <a :href="settingsUrl"><span class="mdi mdi-cog" /> </a></span>
</template>

<script>
import axios from 'axios'

export default {
    name: 'NumberSeriesGetter',
    props: {
        fieldIds: {
            type: Array,
            required: true,
        },
        url: {
            type: String,
            default: '/numberseries/provider/',
        },
        settingsUrl: {
            type: String,
            default: '/numberseries/edit/',
        },
        seriesId: {
            type: [String, Number],
            required: true,
        },
    },
    data() {
        return {
            number: '',
        }
    },
    created() {
        this.getNext()
    },
    methods: {
        use() {
            return axios
                .post(this.url + 'use_next/', {}, { params: { series_id: this.seriesId } })
                .then(response => {
                    const number = response.data.number
                    this.number = response.data.next
                    this.fieldIds.forEach(id => {
                        const input = document.getElementById(id)
                        if (input) input.value = number
                    })
                })
        },
        getNext() {
            return axios.get(this.url + 'get_next/', { params: { series_id: this.seriesId } }).then(response => {
                this.number = response.data.number
            })
        },
    },
}
</script>

<style scoped></style>
