import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const backendHost = process.env.QUANT_BACKEND_PROXY_HOST ?? '127.0.0.1';
const backendPort = process.env.QUANT_BACKEND_PORT ?? '8001';

export default defineConfig({
  plugins: [react()],
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: 'react-vendor',
              test: /node_modules[\\/](react|react-dom|scheduler)[\\/]/,
              priority: 40,
            },
            {
              name: 'chart-vendor',
              test: /node_modules[\\/](echarts|zrender|echarts-for-react)[\\/]/,
              priority: 30,
              maxSize: 450 * 1024,
            },
            {
              name: 'markdown-vendor',
              test: /node_modules[\\/](react-markdown|remark-|micromark|unified|mdast|hast|vfile|unist|entities|property-information|space-separated-tokens|comma-separated-tokens|html-url-attributes|trim-lines|ccount|devlop|bail|trough|is-plain-obj)[\\/]/,
              priority: 25,
            },
            {
              name: 'antd-vendor',
              test: /node_modules[\\/](antd|@ant-design|@rc-component|rc-|dayjs|classnames|copy-to-clipboard|resize-observer-polyfill|throttle-debounce)[\\/]/,
              priority: 20,
              maxSize: 450 * 1024,
            },
            {
              name: 'vendor',
              test: /node_modules[\\/]/,
              priority: 10,
              entriesAware: true,
              maxSize: 450 * 1024,
            },
          ],
        },
      },
    },
  },
  server: {
    proxy: {
      '/api/agent/chat': {
        target: `ws://${backendHost}:${backendPort}`,
        ws: true,
      },
      '/api': {
        target: `http://${backendHost}:${backendPort}`,
        changeOrigin: true,
      },
    },
  },
});
