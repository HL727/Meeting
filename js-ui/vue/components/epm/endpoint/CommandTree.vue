<template>
    <div>
        <v-simple-table
            v-if="isRoot"
            class="mt-5"
        >
            <thead>
                <tr>
                    <th
                        v-translate
                        class="text-left grey-lighten-4"
                    >
                        Kommando
                    </th>
                </tr>
            </thead>
        </v-simple-table>
        <div v-if="nodes.optionNodes.length">
            <CommandWrapper
                v-for="node in nodes.optionNodes"
                :key="node.title + node.options.index"
                :endpoint-id="endpointId"
                :parent="parent"
                :is-root="isRoot"
                :command="node.command"
            />
        </div>

        <div
            v-if="nodes.groupNodes.length"
            class="mt-4"
            :class="{ 'px-4': depth > 0 }"
        >
            <v-expansion-panels
                accordion
                multiple
                :a-value="Object.keys(nodes.groupNodes).map((node) => parseInt(node))"
            >
                <v-expansion-panel
                    v-for="node in nodes.groupNodes"
                    :key="node.key"
                >
                    <v-expansion-panel-header class="px-4">
                        <div>
                            <strong>
                                <span v-if="node.parent && node.parent.parent">{{ node.parent.parent.title }} - </span>
                                <span v-if="node.parent">{{ node.parent.title }} - </span>
                                {{ node.title }}
                                {{ node.options.index > 0 ? node.options.index + 1 : '' }}
                            </strong>
                        </div>
                    </v-expansion-panel-header>
                    <v-expansion-panel-content class="px-0">
                        <v-divider />
                        <CommandTree
                            :depth="depth + 1"
                            :parent="node"
                            :endpoint-id="endpointId"
                            :tree="node.command ? [node.orig] : node.children"
                        />
                    </v-expansion-panel-content>
                </v-expansion-panel>
            </v-expansion-panels>
        </div>

        <div
            v-for="node in nodes.containerNodes"
            :key="node.key"
        >
            <template v-if="node.root && node.childrenContainerNodes.length === 0">
                <CommandTree
                    :depth="depth + 1"
                    :parent="node"
                    :endpoint-id="endpointId"
                    :tree="node.command ? [node.orig] : node.children"
                />
            </template>
            <template v-else>
                <div
                    class="mt-4"
                    :class="{ 'mx-4': node.depth > 0 && node.parent.childrenContainerNodes && node.parent.childrenContainerNodes.length !== 0 }"
                >
                    <v-expansion-panels
                        accordion
                        multiple
                        :value="[0]"
                    >
                        <v-expansion-panel>
                            <v-expansion-panel-header>
                                <div>
                                    <strong>
                                        <span v-if="node.parent && node.parent.parent">{{ node.parent.parent.title }} - </span>
                                        <span v-if="node.parent">{{ node.parent.title }} - </span>
                                        {{ node.title }}
                                        {{ node.options.index > 0 ? node.options.index + 1 : '' }}
                                    </strong>
                                </div>
                            </v-expansion-panel-header>
                            <v-expansion-panel-content class="px-0">
                                <CommandTree
                                    :depth="depth + 1"
                                    :parent="node"
                                    :endpoint-id="endpointId"
                                    :tree="node.command ? [node.orig] : node.children"
                                />
                            </v-expansion-panel-content>
                        </v-expansion-panel>
                    </v-expansion-panels>
                </div>
            </template>
        </div>
    </div>
</template>

<script>
import { filterNodes, filterNodesSorting } from '@/vue/helpers/tree'

import CommandWrapper from './CommandWrapper'

export default {
    name: 'CommandTree',
    components: { CommandWrapper },
    props: {
        tree: { type: Array, default() { return [] } },
        isRoot: { type: Boolean, default: false },
        filter: { type: String, default: '' },
        endpointId: { type: Number, default: null },
        parent: { type: Object, default: () => ({ title: '' }) },
        depth: { type: Number, default: 0 }
    },
    computed: {
        nodes() {
            return this.commandObjects(this.tree)
        },
    },
    methods: {
        getCommands(node) {
            return Object.values(node).filter(n => n.is_command)
        },
        commandObjects(nodes) {
            let index = 0
            const filtered = filterNodes(this.filter, nodes).map(node => {
                const [title, options, children, command] = node
                index += 1

                const childrenOptionNodes = children.filter((node) => node[2].length === 0)
                const childrenGroupNodes = children.filter((node) => node[2].length > 0)
                const childrenContainerNodes = children.filter((node) => node[2].filter((childNode) => childNode[2].length === 0).length > 0)

                const extender = this.depth === 1 && this.parent.childrenOptionNodes.length > 0 && !this.isRoot

                return {
                    index,
                    title,
                    command,
                    options,
                    children,

                    childrenOptionNodes,
                    childrenGroupNodes,
                    childrenContainerNodes,

                    extender,

                    depth: this.depth,
                    parent: this.parent,
                    root: this.isRoot,
                    orig: node,
                    key: options.path.join('>'),
                }
            })

            if (this.isRoot) {
                filtered.sort(filterNodesSorting)
            }

            return this.commandResults(filtered)
        },
        commandResults(filtered) {
            const result = {
                optionNodes: [],
                containerNodes: [],
                groupNodes: [],
            }
            filtered.forEach((node) => {
                if (node.children.length === 0) {
                    return result.optionNodes.push(node)
                }

                let found = false
                node.children.map((childNode) => {
                    if (!found && childNode[2].length === 0) {
                        found = true
                    }
                })

                result[found ? 'groupNodes' : 'containerNodes'].push(node)
            })

            return {
                nodes: filtered,
                ...result
            }
        }
    },
}
</script>
