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
</style>
