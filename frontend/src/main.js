import { createApp } from 'vue'
import { setConfig, frappeRequest, resourcesPlugin } from 'frappe-ui'
import router from './router'
import App from './App.vue'
import './index.css'

setConfig('resourceFetcher', frappeRequest)

createApp(App).use(router).use(resourcesPlugin).mount('#app')
