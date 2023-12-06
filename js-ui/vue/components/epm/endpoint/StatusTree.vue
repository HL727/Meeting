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
                        Option
                    </th>
                    <th
                        v-translate
                        class="text-right"
                    >
                        Värde just nu
                    </th>
                </tr>
            </thead>
        </v-simple-table>
        <v-simple-table v-if="nodes.optionNodes.length">
            <template v-slot:default>
                <tbody>
                    <StatusWrapper
                        v-for="node in nodes.optionNodes"
                        :key="node.title + node.options.index"
                        :checkbox="checkbox"
                        :status="{ name: node.title, value: node.value, path: node.options.path }"
                    />
                </tbody>
            </template>
        </v-simple-table>

        <div
            v-for="node in nodes.groupNodes"
            :key="node.key"
        >
            <div
                v-if="node.extender"
                :class="{ 'mx-4': node.depth > 1 }"
            >
                <v-expansion-panels
                    accordion
                    multiple
                    :value="[0]"
                    class="mb-3"
                >
                    <v-expansion-panel>
                        <v-expansion-panel-header>
                            <strong>
                                <span v-if="node.parent && node.parent.parent">{{ node.parent.parent.title }} - </span>
                                <span v-if="node.parent">{{ node.parent.title }} - </span>
                                {{ node.title }}
                                {{ node.options.item || '' }}
                            </strong>
                        </v-expansion-panel-header>
                        <v-expansion-panel-content class="px-0">
                            <StatusTree
                                :depth="depth + 1"
                                :checkbox="checkbox"
                                :parent="node"
                                :tree="node.children"
                                :filter="filter"
                            />
                        </v-expansion-panel-content>
                    </v-expansion-panel>
                </v-expansion-panels>
            </div>
            <template v-else>
                <v-simple-table :key="node.title + node.options.index">
                    <template v-slot:default>
                        <thead>
                            <tr>
                                <th class="text-left grey-lighten-4 primary--text">
                                    <span v-if="node.parent && node.parent.parent">{{ node.parent.parent.title }} - </span>
                                    <span v-if="node.parent">{{ node.parent.title }} - </span>
                                    <strong>
                                        {{ node.title }}
                                        {{ node.options.item || '' }}
                                    </strong>
                                </th>
                            </tr>
                        </thead>
                    </template>
                </v-simple-table>
                <StatusTree
                    :depth="depth + 1"
                    :checkbox="checkbox"
                    :parent="node"
                    :tree="node.children"
                    :filter="filter"
                />
            </template>
        </div>

        <div
            v-for="node in nodes.containerNodes"
            :key="node.key"
        >
            <div v-if="node.root && node.childrenContainerNodes.length === 0">
                <StatusTree
                    :depth="depth + 1"
                    :checkbox="checkbox"
                    :parent="node"
                    :tree="node.children"
                    :filter="filter"
                />
            </div>
            <div v-else>
                <div
                    class="mb-4"
                    :class="{
                        'mx-4':
                            node.depth > 0 &&
                            node.parent.childrenContainerNodes &&
                            node.parent.childrenContainerNodes.length !== 0,
                    }"
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
                                        {{ node.options.item || '' }}
                                    </strong>
                                </div>
                            </v-expansion-panel-header>
                            <v-expansion-panel-content class="px-0">
                                <StatusTree
                                    :depth="depth + 1"
                                    :checkbox="checkbox"
                                    :parent="node"
                                    :tree="node.children"
                                    :filter="filter"
                                />
                            </v-expansion-panel-content>
                        </v-expansion-panel>
                    </v-expansion-panels>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import { filterNodes, filterNodesSorting } from '@/vue/helpers/tree'

import StatusWrapper from './StatusWrapper'

export default {
    name: 'StatusTree',
    components: { StatusWrapper },
    props: {
        tree: { type: Array, default() { return [] } },
        filter: { type: String, default: '' },
        isRoot: { type: Boolean, default: false },
        checkbox: { type: Boolean, default: false },
        expanding: { type: Boolean, default: false },
        parent: {
            type: Object,
            default: null,
        },
        depth: { type: Number, default: 0 },
    },
    computed: {
        nodes() {
            return this.statusObjects(this.tree)
        },
    },
    methods: {
        statusObjects(nodes) {
            const filtered = filterNodes(this.filter, nodes).map(node => {
                const [title, options, children, value] = node

                const childrenOptionNodes = children.filter(node => node[2].length === 0)
                const childrenGroupNodes = children.filter(node => node[2].length > 0)
                const childrenContainerNodes = children.filter(
                    node => node[2].filter(childNode => childNode[2].length === 0).length > 0
                )

                const extender =
                    this.depth === 1 && this.parent.childrenOptionNodes.length > 0 && !this.isRoot

                return {
                    title,
                    value,
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

            return this.statusResults(filtered)
        },
        statusResults(filtered) {
            const result = {
                optionNodes: [],
                containerNodes: [],
                groupNodes: [],
            }
            filtered.forEach(node => {
                if (node.children.length === 0) {
                    return result.optionNodes.push(node)
                }

                let found = false
                node.children.map(childNode => {
                    if (!found && childNode[2].length === 0) {
                        found = true
                    }
                })

                result[found ? 'groupNodes' : 'containerNodes'].push(node)
            })

            return {
                nodes: filtered,
                ...result,
            }
        }
    },
}
</script>
