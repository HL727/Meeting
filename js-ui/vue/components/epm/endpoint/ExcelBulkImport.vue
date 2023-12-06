<template>
    <div>
        <v-alert
            v-if="error"
            type="error"
        >
            {{ error }}
        </v-alert>

        <form
            v-if="!rows"
            @submit.prevent="upload"
        >
            <v-file-input
                v-model="file"
                :label="$gettext('Välj excelfil')"
            />

            <div class="mt-3">
                <v-btn
                    type="submit"
                    :disabled="!file"
                    color="primary"
                >
                    <translate>Välj kolumner</translate>
                </v-btn>
                <v-btn
                    v-if="!hideClose"
                    class="ml-3"
                    @click="$emit('cancel')"
                >
                    <translate>Stäng</translate>
                </v-btn>
            </div>
        </form>
        <div v-if="rows">
            <v-form @submit.prevent="complete">
                <v-simple-table>
                    <thead>
                        <tr>
                            <th
                                v-for="(h, i) in rows[0]"
                                :key="'header' + i"
                            >
                                <v-select
                                    v-model="headers[i]"
                                    :label="$gettext('Välj kolumn')"
                                    :items="columns"
                                />
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr
                            v-for="(row, y) in rows.slice(skipHeader ? 1 : 0, 10)"
                            :key="'row' + y"
                        >
                            <td
                                v-for="(col, x) in row"
                                :key="`col${y}${x}`"
                            >
                                {{ col }}
                            </td>
                        </tr>
                    </tbody>
                    <tfoot>
                        <tr v-if="rows.length > 10">
                            <td colspan="rows[0].length">
                                <i><translate :translate-params="{count: rows.length - 10}">Samt ytterligare %{count} rader</translate></i>
                            </td>
                        </tr>
                    </tfoot>
                </v-simple-table>
                <v-checkbox
                    v-model="skipHeader"
                    :label="$gettext('Hoppa över första raden')"
                />
                <v-btn
                    :disabled="!hasHeaders"
                    type="submit"
                    color="primary"
                >
                    <translate>Gå vidare</translate>
                </v-btn>
                <v-btn
                    v-if="!hideClose"
                    outlined
                    @click="cancel"
                >
                    <translate>Avbryt</translate>
                </v-btn>
            </v-form>
        </div>
    </div>
</template>

<script>
export default {
    name: 'ExcelBulkImport',
    props: {
        columns: {
            type: Array,
            required: true,
            default() {
                return []
            },
        },
        displayButtons: Boolean,
        hideClose: { type: Boolean, default: false }
    },
    data() {
        return {
            file: null,
            rows: null,
            loading: false,
            skipHeader: false,
            error: '',
            headers: [],
        }
    },
    computed: {
        hasHeaders() {
            return this.headers.some(h => !!h)
        },
    },
    methods: {
        upload() {
            const form = new FormData()
            form.append('file', this.file)
            this.loading = true
            this.error = ''
            this.$store
                .api()
                .post('excel/read/', form)
                .then(response => {
                    this.rows = response
                    if (this.rows.length && this.headers.length < this.rows[0].length) {
                        this.headers = this.headers.concat(new Array(this.rows[0].length - this.headers.length))
                    }
                    this.loading = false
                })
                .catch(e => {
                    this.error = e.toString()
                })
        },
        matchHeaders(rows) {
            if (!rows || !rows.length) return
            this.headers = rows[0].map(col => {
                const firstWord = (col || '').toLocaleLowerCase().split(/[- ]/)[0]
                let result = ''
                this.columns.forEach(x => {
                    if (
                        x.text.toLocaleLowerCase().includes(firstWord) ||
                        x.value.toLocaleLowerCase().includes(firstWord)
                    ) {
                        result = x.value
                    }
                })
                return result
            })
        },
        cancel() {
            if (this.rows) {
                this.rows = null
                this.$emit('cancel')
            }
        },
        complete() {
            this.$emit('input', this.compile(this.rows).slice(this.skipHeader ? 1 : 0))
            this.$emit('complete')
            this.rows = null
        },
        compile(rows) {
            return (rows || []).map(item => {
                const cur = {}
                this.headers.forEach((header, index) => {
                    if (header && index < item.length) {
                        cur[header] = item[index]
                    }
                })
                return cur
            })
        },
    },
}
</script>

<style scoped></style>
