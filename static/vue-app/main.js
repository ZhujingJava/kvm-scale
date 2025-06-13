// static/vue-app/main.js
const { createApp } = Vue;

createApp({
  data() {
    return {
      vms: [],
      selectedHost: null
    };
  },
  mounted() {
    const urlParams = new URLSearchParams(window.location.search);
    this.selectedHost = urlParams.get('host');

    if (!this.selectedHost) {
      alert("请传入 host 参数");
      return;
    }

    // 请求数据
    fetch(`/api/kvm/list?host=${this.selectedHost}`)
      .then(res => res.json())
      .then(data => {
        if (data.error) {
          alert(data.error);
        } else {
          this.vms = data.vms || [];
        }
      })
      .catch(err => {
        console.error(err);
        alert("请求失败：" + err.message);
      });
  }
}).mount('#app');
