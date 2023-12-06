/**
 * Global event bus. Initialize in data() { return { emitter: new GlobalEmitter(this), } }
 */
export class GlobalEventBus {
    constructor(vm) {
        this.vm = vm
        this.counter = vm.$route.meta.counter
    }

    emit(eventType, ...args) {
        this.vm.$root.$emit(eventType, {
            counter: this.counter,
            args,
        })
    }

    on(eventType, callback) {
        const vm = this.vm

        const validateCallback = eventData => {
            if (eventData.counter !== vm.$root.$route.meta.counter) {
                return
            }
            return callback.apply(vm, eventData.args)
        }
        vm.$once('hook:beforeDestroy', () => {
            vm.$root.$off(eventType, validateCallback)
        })
        vm.$root.$on(eventType, validateCallback)
    }

}

export function globalOn(vm, eventType, callback) {
    return new GlobalEventBus(vm).on(eventType, callback)
}
export function globalEmit(vm, eventType, ...args) {
    return new GlobalEventBus(vm).emit(eventType, ...args)
}
