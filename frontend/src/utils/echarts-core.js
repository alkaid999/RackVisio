// echarts 按需引入（H-07）：全量 `import * as echarts` 使 Dashboard chunk 达 1.1MB。
// 本项目仅使用 pie / treemap / bar 三类图表，改用 echarts/core + use() 注册，
// 产物体积约砍 60%。新增图表类型时在此追加注册。
import * as echarts from 'echarts/core'
import { BarChart, PieChart, TreemapChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { LabelLayout } from 'echarts/features'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  BarChart,
  PieChart,
  TreemapChart,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  LabelLayout,
  CanvasRenderer,
])

export default echarts
