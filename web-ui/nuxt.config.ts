// https://nuxt.com/docs/api/configuration/nuxt-config
import vuetify, { transformAssetUrls } from 'vite-plugin-vuetify'

export default defineNuxtConfig({
  compatibilityDate: '2025-07-01',
  devtools: { enabled: true },

  modules: [
    '@pinia/nuxt',
    (_options, nuxt) => {
      nuxt.hooks.hook('vite:extendConfig', (config) => {
        // @ts-expect-error
        config.plugins.push(vuetify({ autoImport: true }))
      })
    },
  ],

  css: [
    'vuetify/styles',
    '@mdi/font/css/materialdesignicons.css',
  ],

  build: {
    transpile: ['vuetify'],
  },

  ssr: false,

  app: {
    head: {
      title: 'WoWS Replay Database',
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'description', content: 'World of Warships Replay Database and Analysis Tool' }
      ],
    }
  },

  runtimeConfig: {
    public: {
      apiBaseUrl: process.env.API_BASE_URL || '',
      s3BucketUrl: process.env.S3_BUCKET_URL || '',
    }
  },

  vite: {
    define: {
      'process.env.DEBUG': false,
    },
  },

  // Nitro設定
  nitro: {
    publicAssets: [
      {
        dir: 'public',
        maxAge: 60 * 60 * 24 * 7, // 1 week
      },
    ],
  },

  // ルートルール
  routeRules: {
    '/robots.txt': { prerender: true },
  },
})
