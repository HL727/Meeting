<script>
import { $gettext } from '@/vue/helpers/translate'

export default {
    computed: {
        license() {
            return this.$store.getters['site/license']
        },
        baseStatus() {
            return this.license.status.base.active
        },
        licenseStatus() {
            return this.license.status['epm:endpoint'] || {}
        },
        licenseOveruse() {
            return this.licenseStatus.status === 'limit'
        },
        licenseHasDetails() {
            return 'active' in this.licenseStatus && 'licensed' in this.licenseStatus
        },
        licenseDevicesLeft() {
            const devicesLeft = this.licenseStatus.licensed - this.licenseStatus.active
            return devicesLeft < 0 ? 0 : devicesLeft
        },
        licenseProgress() {
            if (this.licenseOveruse || !this.licenseHasDetails) return 100

            return (this.licenseStatus.active / this.licenseStatus.licensed) * 100
        },
        licenseError() {
            if (this.licenseOveruse && this.licenseStatus.licensed !== -1) {
                return $gettext('Ni har registrerat så många system som er licens tillåter, vänligen kontakta er partner.')
            }
            return ''
        }
    }
}
</script>
