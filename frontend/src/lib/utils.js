import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * 合并 Tailwind 类名：clsx 处理条件类名，twMerge 去重冲突类（如同时写 px-2 px-4 取后者）。
 * shadcn-vue 标准工具，组件内统一通过 cn() 拼接变体样式。
 */
export function cn(...inputs) {
  return twMerge(clsx(inputs))
}
