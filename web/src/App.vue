<template>
  <el-container style="height: 100vh">
    <!-- Sidebar -->
    <el-aside width="200px" style="background: #1d2b55">
      <div style="padding: 20px; text-align: center; color: #fff; font-size: 18px; font-weight: bold; border-bottom: 1px solid rgba(255,255,255,0.1)">
        💳 信用卡管理
      </div>
      <el-menu
        :default-active="route.path"
        background-color="#1d2b55"
        text-color="#a0aec0"
        active-text-color="#4fd1c5"
        router
      >
        <el-menu-item index="/dashboard">
          <span>📊 仪表盘</span>
        </el-menu-item>
        <el-menu-item index="/calendar">
          <span>📅 还款日历</span>
        </el-menu-item>
        <el-menu-item index="/report">
          <span>📋 账单报表</span>
        </el-menu-item>
        <el-menu-item index="/history">
          <span>📜 还款历史</span>
        </el-menu-item>
        <el-menu-item index="/suggest">
          <span>💡 还款建议</span>
        </el-menu-item>
        <el-menu-item index="/pay">
          <span>✅ 标记还款</span>
        </el-menu-item>
        <el-menu-item index="/health">
          <span>🩺 健康记录</span>
        </el-menu-item>
        <el-menu-item index="/annual-fees">
          <span>💰 年费管理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- Main content -->
    <el-main style="background: #f5f7fa; padding: 20px">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { useRoute } from 'vue-router'
const route = useRoute()
</script>

<style>
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
.el-aside .el-menu { border-right: none; }

/* 打印时隐藏侧边栏，只显示打印区域 */
@media print {
  @page { size: landscape; margin: 10mm; }
  .el-aside { display: none !important; }
  .el-main { padding: 0 !important; background: #fff !important; }
  /* 隐藏侧边栏和所有非打印内容 */
  .el-aside, .no-print, .screen-chart { display: none !important; }
  /* 显示打印区域 */
  #print-area { display: block !important; }
}
</style>
