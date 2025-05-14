// 尾盘选股八大步骤 Web应用
const { createApp, ref, reactive, computed, onMounted, onUnmounted, nextTick } = Vue;

// 创建Socket.io实例
const socket = io();

// 定义八大步骤描述
const FILTER_STEPS = [
    {
        title: "涨幅筛选",
        condition: "3%-5%",
        proExplanation: "筛选日内涨幅在3%到5%之间的股票，避免涨幅过大风险和过小无动力",
        simpleExplanation: "股票今天涨了，但不是涨太多也不是涨太少，处于'金发姑娘区间'",
        icon: "📈"
    },
    {
        title: "量比筛选",
        condition: "> 1.0",
        proExplanation: "量比大于1.0表示当日成交量高于最近5日平均成交量，说明交投活跃",
        simpleExplanation: "今天的交易比平时更活跃，有更多人在买卖这只股票",
        icon: "📊"
    },
    {
        title: "换手率筛选",
        condition: "5%-10%",
        proExplanation: "换手率表示当日成交股数占流通股本的百分比，反映市场活跃度",
        simpleExplanation: "今天有适当比例的股票易主，既不是少得没人要，也不是多到疯狂炒作",
        icon: "🔄"
    },
    {
        title: "市值筛选",
        condition: "50亿-200亿",
        proExplanation: "中等市值具有足够流动性又不会资金推动困难",
        simpleExplanation: "公司规模适中，既不是小到不稳定，也不是大到难以上涨",
        icon: "💰"
    },
    {
        title: "成交量筛选",
        condition: "持续放大",
        proExplanation: "连续几日成交量呈现放大趋势，表明买入意愿增强",
        simpleExplanation: "最近几天越来越多的人在交易这只股票，关注度在提升",
        icon: "📶"
    },
    {
        title: "均线形态筛选",
        condition: "短期均线搭配60日线向上",
        proExplanation: "MA5>MA10>MA20>MA60且MA60向上，是典型多头排列形态",
        simpleExplanation: "股价的各种平均线呈现向上的阶梯状，表明上涨趋势健康",
        icon: "📈"
    },
    {
        title: "大盘强度筛选",
        condition: "强于大盘",
        proExplanation: "个股涨幅持续强于上证指数，表现出相对强势",
        simpleExplanation: "这只股票表现比整体市场更好，有独立上涨能力",
        icon: "💪"
    },
    {
        title: "尾盘创新高筛选",
        condition: "尾盘接近日内高点",
        proExplanation: "尾盘价格接近当日最高价(≥95%)，表明上涨势头强劲",
        simpleExplanation: "收盘前股价仍然保持在当天的高位，说明看好的人更多",
        icon: "🏆"
    }
];

// 主应用
const App = {
    setup() {
        // 应用状态
        const appLoaded = ref(false);
        const systemStatus = reactive({
            time: '',
            marketStatus: '待检测',
            isTailMarket: false
        });
        
        // 筛选配置
        const filterConfig = reactive({
            market: 'SH',
            apiSource: 'sina',
            degradationEnabled: false,
            degradationLevel: 'MEDIUM'
        });
        
        // 可用市场列表
        const marketOptions = ref([]);
        
        // 数据源选项
        const apiOptions = [
            { value: 'sina', label: '新浪财经(推荐)' },
            { value: 'hexun', label: '和讯财经' },
            { value: 'alltick', label: 'AllTick API' }
        ];
        
        // 降级级别选项
        const degradationOptions = [
            { value: 'LOW', label: '轻度 (仅允许高可靠性数据源替代)' },
            { value: 'MEDIUM', label: '中度 (允许替代数据分析方法)' },
            { value: 'HIGH', label: '重度 (允许所有降级策略)' }
        ];
        
        // 筛选状态
        const filterState = reactive({
            isRunning: false,
            progress: 0,
            currentStep: -1,
            status: 'ready',
            message: '就绪',
            results: [],
            partialMatch: false,
            maxStep: 0
        });
        
        // 日志消息
        const logs = ref([]);
        
        // 选中的股票
        const selectedStock = ref(null);
        
        // 表格列定义
        const tableColumns = [
            { prop: 'code', label: '代码', width: '100' },
            { prop: 'name', label: '名称', width: '120' },
            { prop: 'price', label: '价格', width: '90' },
            { prop: 'change_pct', label: '涨跌幅(%)', width: '100' },
            { prop: 'volume', label: '成交量', width: '120' },
            { prop: 'turnover_rate', label: '换手率(%)', width: '100' },
            { prop: 'market_cap', label: '市值(亿)', width: '100' },
            { prop: 'quality_text', label: '数据质量', width: '100' }
        ];
        
        // K线图实例
        let klineChart = null;
        
        // 自动更新时间和市场状态
        let clockTimer = null;
        
        // 获取系统状态
        const fetchSystemStatus = async () => {
            try {
                const response = await axios.get('/api/system/status');
                const data = response.data;
                
                systemStatus.time = data.time;
                systemStatus.marketStatus = data.market_status;
                systemStatus.isTailMarket = data.is_tail_market;
                
                // 如果是尾盘时段且没有在运行筛选，自动提示
                if (data.is_tail_market && !filterState.isRunning) {
                    addLog('当前是尾盘时段，建议开始筛选', 'info');
                }
            } catch (error) {
                console.error('获取系统状态失败:', error);
            }
        };
        
        // 获取可用市场
        const fetchMarkets = async () => {
            try {
                const response = await axios.get('/api/stock/markets');
                marketOptions.value = response.data;
            } catch (error) {
                console.error('获取可用市场失败:', error);
                marketOptions.value = [
                    { value: 'SH', label: '上证' },
                    { value: 'SZ', label: '深证' },
                    { value: 'BJ', label: '北证' },
                    { value: 'HK', label: '港股' },
                    { value: 'US', label: '美股' }
                ];
            }
        };
        
        // 添加日志消息
        const addLog = (message, type = 'info') => {
            const timestamp = new Date().toLocaleTimeString();
            logs.value.unshift({
                id: Date.now(),
                timestamp,
                message,
                type
            });
            
            // 限制日志数量
            if (logs.value.length > 100) {
                logs.value = logs.value.slice(0, 100);
            }
        };
        
        // 开始筛选
        const startFilter = async () => {
            if (filterState.isRunning) {
                ElMessage.warning('筛选正在进行中，请稍候...');
                return;
            }
            
            try {
                // 重置筛选状态
                filterState.isRunning = true;
                filterState.progress = 0;
                filterState.currentStep = -1;
                filterState.status = 'initializing';
                filterState.message = '筛选准备中...';
                filterState.results = [];
                filterState.partialMatch = false;
                filterState.maxStep = 0;
                
                // 发送筛选请求
                const response = await axios.post('/api/stock/filter', {
                    market: filterConfig.market,
                    api_source: filterConfig.apiSource,
                    degradation_enabled: filterConfig.degradationEnabled,
                    degradation_level: filterConfig.degradationLevel
                });
                
                if (response.data.status === 'started') {
                    addLog('筛选流程已启动', 'success');
                } else {
                    addLog(`筛选请求失败: ${response.data.message}`, 'error');
                    filterState.isRunning = false;
                }
            } catch (error) {
                console.error('开始筛选失败:', error);
                addLog(`筛选请求错误: ${error.message}`, 'error');
                filterState.isRunning = false;
            }
        };
        
        // 导出结果为CSV
        const exportResults = async () => {
            if (!filterState.results || filterState.results.length === 0) {
                ElMessage.warning('没有可导出的数据');
                return;
            }
            
            try {
                // 获取数据
                const response = await axios.get('/api/stock/export');
                const data = response.data;
                
                // 转换为CSV
                const headers = ['代码', '名称', '价格', '涨跌幅(%)', '成交量', '换手率(%)', '市值(亿)'];
                const csvContent = [
                    headers.join(','),
                    ...data.map(stock => [
                        stock.code,
                        stock.name,
                        stock.price.toFixed(2),
                        stock.change_pct.toFixed(2),
                        stock.volume,
                        stock.turnover_rate.toFixed(2),
                        stock.market_cap.toFixed(2)
                    ].join(','))
                ].join('\n');
                
                // 创建下载链接
                const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                const timestamp = new Date().toISOString().replace(/[-:.]/g, '').substring(0, 14);
                
                link.href = url;
                link.setAttribute('download', `尾盘选股结果_${timestamp}.csv`);
                document.body.appendChild(link);
                
                // 触发下载
                link.click();
                
                // 清理
                document.body.removeChild(link);
                URL.revokeObjectURL(url);
                
                ElMessage.success('导出成功');
            } catch (error) {
                console.error('导出失败:', error);
                ElMessage.error(`导出失败: ${error.message}`);
            }
        };
        
        // 选择股票
        const selectStock = async (stock) => {
            selectedStock.value = stock;
            
            // 获取K线数据并绘制
            await fetchKlineData(stock.code);
        };
        
        // 获取K线数据
        const fetchKlineData = async (stockCode) => {
            try {
                const response = await axios.get(`/api/stock/kline/${stockCode}`, {
                    params: {
                        type: 1,
                        periods: 60
                    }
                });
                
                const klineData = response.data;
                
                // 绘制K线图
                drawKlineChart(klineData);
            } catch (error) {
                console.error('获取K线数据失败:', error);
                ElMessage.error(`获取K线数据失败: ${error.message}`);
            }
        };
        
        // 绘制K线图
        const drawKlineChart = (klineData) => {
            if (!selectedStock.value) return;
            
            // 确保图表容器存在
            nextTick(() => {
                const chartContainer = document.getElementById('klineChart');
                if (!chartContainer) return;
                
                // 销毁旧图表实例
                if (klineChart) {
                    klineChart.dispose();
                }
                
                // 提取数据
                const klineValues = klineData.data || [];
                const metadata = klineData.metadata || {};
                
                // 如果没有数据，显示错误消息
                if (!klineValues || klineValues.length === 0) {
                    // 创建空图表
                    klineChart = echarts.init(chartContainer);
                    klineChart.setOption({
                        title: {
                            text: `${selectedStock.value.code} 无法获取K线数据`,
                            left: 'center'
                        }
                    });
                    return;
                }
                
                // 提取数据点
                const dates = klineValues.map(k => new Date(k.timestamp * 1000).toLocaleDateString());
                const data = klineValues.map(k => [k.open, k.close, k.low, k.high]);
                
                // 计算移动平均线
                const calculateMA = (values, dayCount) => {
                    const result = [];
                    for (let i = 0; i < values.length; i++) {
                        if (i < dayCount - 1) {
                            result.push('-');
                            continue;
                        }
                        let sum = 0;
                        for (let j = 0; j < dayCount; j++) {
                            sum += values[i - j][1];
                        }
                        result.push((sum / dayCount).toFixed(2));
                    }
                    return result;
                };
                
                // 初始化图表
                klineChart = echarts.init(chartContainer);
                
                // 设置图表选项
                klineChart.setOption({
                    title: {
                        text: `${selectedStock.value.code} ${selectedStock.value.name} 日K线`,
                        subtext: `数据来源: ${metadata.source_text || metadata.source || '未知'} (${metadata.reliability_text || '未知可靠性'})`,
                        left: 'center'
                    },
                    tooltip: {
                        trigger: 'axis',
                        axisPointer: {
                            type: 'cross'
                        }
                    },
                    legend: {
                        data: ['K线', 'MA5', 'MA10', 'MA20'],
                        top: 30
                    },
                    grid: {
                        left: '10%',
                        right: '10%',
                        bottom: '15%'
                    },
                    xAxis: {
                        type: 'category',
                        data: dates,
                        scale: true,
                        boundaryGap: false,
                        axisLine: { onZero: false },
                        splitLine: { show: false },
                        splitNumber: 20,
                        min: 'dataMin',
                        max: 'dataMax'
                    },
                    yAxis: {
                        scale: true,
                        splitArea: {
                            show: true
                        }
                    },
                    dataZoom: [
                        {
                            type: 'inside',
                            start: 50,
                            end: 100
                        },
                        {
                            show: true,
                            type: 'slider',
                            top: '90%',
                            start: 50,
                            end: 100
                        }
                    ],
                    series: [
                        {
                            name: 'K线',
                            type: 'candlestick',
                            data: data,
                            itemStyle: {
                                color: '#ec0000',
                                color0: '#00da3c',
                                borderColor: '#8A0000',
                                borderColor0: '#008F28'
                            }
                        },
                        {
                            name: 'MA5',
                            type: 'line',
                            data: calculateMA(data, 5),
                            smooth: true,
                            lineStyle: {
                                opacity: 0.5
                            }
                        },
                        {
                            name: 'MA10',
                            type: 'line',
                            data: calculateMA(data, 10),
                            smooth: true,
                            lineStyle: {
                                opacity: 0.5
                            }
                        },
                        {
                            name: 'MA20',
                            type: 'line',
                            data: calculateMA(data, 20),
                            smooth: true,
                            lineStyle: {
                                opacity: 0.5
                            }
                        }
                    ]
                });
            });
        };
        
        // 处理WebSocket事件
        const setupSocketEvents = () => {
            // 筛选进度更新
            socket.on('filter_progress', (data) => {
                // 更新筛选状态
                filterState.status = data.status;
                filterState.message = data.message;
                filterState.progress = data.progress;
                filterState.currentStep = data.current_step;
                
                // 记录日志
                addLog(data.message, data.status === 'error' ? 'error' : 'info');
                
                // 如果有筛选结果
                if (data.results && data.results.length > 0) {
                    filterState.results = data.results;
                    filterState.partialMatch = data.partial_match || false;
                    filterState.maxStep = data.max_step || 8;
                    
                    // 如果筛选成功或有部分结果，选择第一个股票
                    if (['success', 'partial_results', 'fallback_results'].includes(data.status)) {
                        nextTick(() => {
                            if (filterState.results.length > 0) {
                                selectStock(filterState.results[0]);
                            }
                        });
                        
                        // 标记筛选结束
                        filterState.isRunning = false;
                    }
                }
                
                // 如果发生错误，标记筛选结束
                if (data.status === 'error') {
                    filterState.isRunning = false;
                }
            });
        };
        
        // 组件挂载时的钩子
        onMounted(() => {
            // 设置应用已加载
            appLoaded.value = true;
            
            // 初始化数据
            fetchMarkets();
            fetchSystemStatus();
            
            // 设置WebSocket事件
            setupSocketEvents();
            
            // 设置定时更新系统状态
            clockTimer = setInterval(() => {
                fetchSystemStatus();
            }, 30000); // 每30秒更新一次
            
            // 添加初始日志
            addLog('尾盘选股八大步骤应用已启动', 'info');
        });
        
        // 组件卸载时的钩子
        onUnmounted(() => {
            // 清除定时器
            if (clockTimer) clearInterval(clockTimer);
            
            // 清除K线图实例
            if (klineChart) klineChart.dispose();
            
            // 断开WebSocket
            if (socket) socket.disconnect();
        });
        
        // 返回模板需要的数据和方法
        return {
            appLoaded,
            systemStatus,
            filterConfig,
            marketOptions,
            apiOptions,
            degradationOptions,
            filterState,
            logs,
            tableColumns,
            selectedStock,
            FILTER_STEPS,
            startFilter,
            exportResults,
            selectStock,
            addLog
        };
    },
    template: `
        <div class="stock-app">
            <!-- 顶部标题区 -->
            <el-row :gutter="20" class="mb-4">
                <el-col :span="18">
                    <h1>尾盘选股八大步骤</h1>
                </el-col>
                <el-col :span="6" class="text-right">
                    <div class="system-status">
                        <div>当前时间: {{ systemStatus.time }}</div>
                        <div :class="{'market-tail': systemStatus.isTailMarket}">
                            交易状态: {{ systemStatus.marketStatus }}
                        </div>
                    </div>
                </el-col>
            </el-row>
            
            <!-- 主内容区 -->
            <el-row :gutter="20">
                <!-- 左侧控制面板 -->
                <el-col :span="6">
                    <el-card class="box-card mb-4">
                        <template #header>
                            <div class="card-header">
                                <span>数据源设置</span>
                            </div>
                        </template>
                        
                        <!-- API选择 -->
                        <div class="mb-3">
                            <el-radio-group v-model="filterConfig.apiSource" size="large">
                                <el-radio-button 
                                    v-for="option in apiOptions" 
                                    :key="option.value" 
                                    :label="option.value"
                                >
                                    {{ option.label }}
                                </el-radio-button>
                            </el-radio-group>
                        </div>
                        
                        <!-- AllTick Token输入框 -->
                        <div v-if="filterConfig.apiSource === 'alltick'" class="mb-3">
                            <el-input placeholder="输入AllTick API Token" size="large">
                                <template #append>
                                    <el-button>设置</el-button>
                                </template>
                            </el-input>
                        </div>
                        
                        <!-- 数据降级策略 -->
                        <div class="mb-3">
                            <el-switch
                                v-model="filterConfig.degradationEnabled"
                                active-text="允许数据降级"
                                size="large"
                            />
                        </div>
                        
                        <!-- 降级程度 -->
                        <div v-if="filterConfig.degradationEnabled">
                            <el-radio-group v-model="filterConfig.degradationLevel" size="large">
                                <el-radio 
                                    v-for="option in degradationOptions" 
                                    :key="option.value" 
                                    :label="option.value"
                                >
                                    {{ option.label }}
                                </el-radio>
                            </el-radio-group>
                        </div>
                    </el-card>
                    
                    <el-card class="box-card mb-4">
                        <template #header>
                            <div class="card-header">
                                <span>筛选控制</span>
                            </div>
                        </template>
                        
                        <!-- 市场选择 -->
                        <div class="mb-3">
                            <el-radio-group v-model="filterConfig.market" size="large">
                                <el-radio 
                                    v-for="option in marketOptions" 
                                    :key="option.value" 
                                    :label="option.value"
                                >
                                    {{ option.label }}
                                </el-radio>
                            </el-radio-group>
                        </div>
                        
                        <!-- 开始筛选按钮 -->
                        <el-button 
                            type="danger" 
                            size="large" 
                            :loading="filterState.isRunning"
                            @click="startFilter"
                            style="width: 100%;"
                        >
                            {{ filterState.isRunning ? '筛选中...' : '开始筛选' }}
                        </el-button>
                        
                        <!-- 导出结果按钮 -->
                        <el-button 
                            type="primary" 
                            size="large" 
                            style="width: 100%; margin-top: 10px;"
                            :disabled="!filterState.results.length"
                            @click="exportResults"
                        >
                            导出结果到CSV
                        </el-button>
                    </el-card>
                    
                    <el-card class="box-card">
                        <template #header>
                            <div class="card-header">
                                <span>筛选日志</span>
                            </div>
                        </template>
                        
                        <div class="log-container" style="height: 300px; overflow-y: auto;">
                            <div 
                                v-for="log in logs" 
                                :key="log.id" 
                                class="log-item"
                                :class="'log-' + log.type"
                            >
                                <span class="log-time">[{{ log.timestamp }}]</span>
                                <span class="log-message">{{ log.message }}</span>
                            </div>
                            <div v-if="!logs.length" class="empty-log">
                                暂无日志记录
                            </div>
                        </div>
                    </el-card>
                </el-col>
                
                <!-- 右侧数据展示区 -->
                <el-col :span="18">
                    <!-- 筛选进度 -->
                    <el-card v-if="filterState.isRunning || filterState.results.length > 0" class="box-card mb-4">
                        <template #header>
                            <div class="card-header">
                                <span>筛选进度</span>
                                <span>{{ filterState.message }}</span>
                            </div>
                        </template>
                        
                        <el-progress 
                            :percentage="filterState.progress" 
                            :status="filterState.status === 'error' ? 'exception' : 
                                   (filterState.status === 'success' ? 'success' : '')"
                        />
                        
                        <!-- 步骤展示 -->
                        <div class="steps-container" style="margin-top: 20px;">
                            <el-steps :active="filterState.currentStep + 1" finish-status="success">
                                <el-step 
                                    v-for="(step, index) in FILTER_STEPS" 
                                    :key="index" 
                                    :title="step.title"
                                    :description="step.condition"
                                />
                            </el-steps>
                        </div>
                    </el-card>
                    
                    <!-- 筛选结果 -->
                    <el-card v-if="filterState.results.length > 0" class="box-card mb-4">
                        <template #header>
                            <div class="card-header">
                                <span>筛选结果</span>
                                <span v-if="filterState.partialMatch" class="warning-text">
                                    (部分匹配: 符合前{{ filterState.maxStep }}步)
                                </span>
                                <span v-else class="success-text">
                                    (完全匹配)
                                </span>
                            </div>
                        </template>
                        
                        <el-table 
                            :data="filterState.results" 
                            style="width: 100%"
                            height="350"
                            @row-click="selectStock"
                            :highlight-current-row="true"
                            row-key="code"
                        >
                            <el-table-column 
                                v-for="column in tableColumns"
                                :key="column.prop"
                                :prop="column.prop"
                                :label="column.label"
                                :width="column.width"
                            >
                                <template #default="scope">
                                    <!-- 格式化不同类型的列 -->
                                    <template v-if="column.prop === 'price'">
                                        {{ scope.row[column.prop].toFixed(2) }}
                                    </template>
                                    <template v-else-if="column.prop === 'change_pct'">
                                        <span :class="scope.row[column.prop] >= 0 ? 'up-text' : 'down-text'">
                                            {{ scope.row[column.prop].toFixed(2) }}%
                                        </span>
                                    </template>
                                    <template v-else-if="column.prop === 'turnover_rate'">
                                        {{ scope.row[column.prop].toFixed(2) }}%
                                    </template>
                                    <template v-else-if="column.prop === 'market_cap'">
                                        {{ scope.row[column.prop].toFixed(2) }}
                                    </template>
                                    <template v-else-if="column.prop === 'volume'">
                                        {{ scope.row[column.prop].toLocaleString() }}
                                    </template>
                                    <template v-else-if="column.prop === 'quality_text'">
                                        <el-tag :type="
                                            scope.row.quality_level === 'high' ? 'success' :
                                            scope.row.quality_level === 'medium' ? 'warning' : 'danger'
                                        " size="small">
                                            {{ scope.row[column.prop] }}
                                        </el-tag>
                                    </template>
                                    <template v-else>
                                        {{ scope.row[column.prop] }}
                                    </template>
                                </template>
                            </el-table-column>
                        </el-table>
                    </el-card>
                    
                    <!-- 股票详情展示 -->
                    <el-card v-if="selectedStock" class="box-card">
                        <template #header>
                            <div class="card-header">
                                <span>{{ selectedStock.name }}({{ selectedStock.code }}) 详情</span>
                                <span class="quality-tag">
                                    <el-tag :type="
                                        selectedStock.quality_level === 'high' ? 'success' :
                                        selectedStock.quality_level === 'medium' ? 'warning' : 'danger'
                                    " size="small">
                                        {{ selectedStock.quality_text }}
                                    </el-tag>
                                </span>
                            </div>
                        </template>
                        
                        <el-tabs>
                            <el-tab-pane label="K线图">
                                <div id="klineChart" style="width: 100%; height: 400px;"></div>
                            </el-tab-pane>
                            <el-tab-pane label="详细数据">
                                <el-descriptions :column="2" border>
                                    <el-descriptions-item label="股票代码">{{ selectedStock.code }}</el-descriptions-item>
                                    <el-descriptions-item label="股票名称">{{ selectedStock.name }}</el-descriptions-item>
                                    <el-descriptions-item label="当前价格">{{ selectedStock.price.toFixed(2) }}</el-descriptions-item>
                                    <el-descriptions-item label="涨跌幅">
                                        <span :class="selectedStock.change_pct >= 0 ? 'up-text' : 'down-text'">
                                            {{ selectedStock.change_pct.toFixed(2) }}%
                                        </span>
                                    </el-descriptions-item>
                                    <el-descriptions-item label="成交量">{{ selectedStock.volume.toLocaleString() }}</el-descriptions-item>
                                    <el-descriptions-item label="换手率">{{ selectedStock.turnover_rate.toFixed(2) }}%</el-descriptions-item>
                                    <el-descriptions-item label="市值(亿)">{{ selectedStock.market_cap.toFixed(2) }}</el-descriptions-item>
                                    <el-descriptions-item label="量比">{{ (selectedStock.volume_ratio || 0).toFixed(2) }}</el-descriptions-item>
                                    <el-descriptions-item label="数据质量">{{ selectedStock.quality_text }}</el-descriptions-item>
                                    <el-descriptions-item label="更新时间">{{ selectedStock.update_time }}</el-descriptions-item>
                                </el-descriptions>
                            </el-tab-pane>
                        </el-tabs>
                    </el-card>
                </el-col>
            </el-row>
        </div>
    `
};

// 创建Vue应用并挂载
const app = createApp({
    setup() {
        const appLoaded = ref(false);
        
        onMounted(() => {
            setTimeout(() => {
                appLoaded.value = true;
            }, 1000);
        });
        
        return {
            appLoaded
        };
    },
    components: {
        App
    },
    template: `
        <div>
            <div v-if="!appLoaded" class="loading-container">
                <el-progress type="dashboard" :percentage="100" status="success" :indeterminate="true" />
                <div class="loading-text">尾盘选股八大步骤应用加载中...</div>
            </div>
            <App v-else />
        </div>
    `
});

// 注册ElementPlus
app.use(ElementPlus);

// 挂载应用
app.mount('#app');

// 添加全局样式
document.head.insertAdjacentHTML('beforeend', `
<style>
    .mb-4 {
        margin-bottom: 16px;
    }
    .text-right {
        text-align: right;
    }
    .system-status {
        text-align: right;
        line-height: 1.5;
    }
    .market-tail {
        color: #E6A23C;
        font-weight: bold;
    }
    .log-container {
        font-family: monospace;
        font-size: 12px;
    }
    .log-item {
        padding: 4px 0;
        border-bottom: 1px solid #eee;
    }
    .log-time {
        color: #999;
        margin-right: 5px;
    }
    .log-info .log-message {
        color: #333;
    }
    .log-warning .log-message {
        color: #E6A23C;
    }
    .log-error .log-message {
        color: #F56C6C;
    }
    .log-success .log-message {
        color: #67C23A;
    }
    .empty-log {
        color: #999;
        text-align: center;
        padding: 20px 0;
    }
    .up-text {
        color: #F56C6C;
    }
    .down-text {
        color: #67C23A;
    }
    .warning-text {
        color: #E6A23C;
        font-size: 14px;
        margin-left: 10px;
    }
    .success-text {
        color: #67C23A;
        font-size: 14px;
        margin-left: 10px;
    }
    .quality-tag {
        margin-left: 10px;
    }
</style>
`); 