document.addEventListener("DOMContentLoaded", function () {
    const kvmTable = document.getElementById("kvm-table");

    if (kvmTable) {
        const tbody = kvmTable.querySelector("tbody");
        const hostIp = document.body.dataset.hostIp;
        const totalCpuEl = document.getElementById("total-cpu");
        const totalMemEl = document.getElementById("total-memory");

        if (!hostIp || hostIp === "mock") {
            console.warn("❌ hostIp 为空或为 mock，不加载数据");
            return;
        }

        tbody.innerHTML = '<tr><td colspan="6" class="text-center">正在加载...</td></tr>';

        // 初始化总计
        let totalRunningCpu = 0;
        let totalRunningMemory = 0;

        fetch(`/api/kvm/list?host=${hostIp}`)
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                return response.json();
            })
            .then(data => {
                tbody.innerHTML = "";
                if (!data || data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" class="text-center">该主机上没有找到虚拟机。</td></tr>';
                    return;
                }

                data.forEach(vm => {
                    const stateText = vm.state === 'running' ?
                        '<span class="badge bg-success">运行中</span>' :
                        '<span class="badge bg-secondary">已关机</span>';

                    const elasticCpu = vm.elastic_vcpu ? `<span class="badge bg-success">支持</span>` : `<span class="badge bg-secondary">不支持</span>`;
                    const elasticMemory = vm.elastic_memory ? `<span class="badge bg-success">支持</span>` : `<span class="badge bg-secondary">不支持</span>`;
                    const isElasticEnabled = vm.elastic_vcpu || vm.elastic_mem_gb ? "" : "disabled";
                    const qemuGaStatus = vm.has_qemu_ga ?
                        '<span class="badge bg-success">已安装</span>' :
                        '<span class="badge bg-secondary">未安装</span>';

                    const row = document.createElement("tr");
                    row.innerHTML = `
                        <td>${vm.name}</td>
                        <td>${stateText}</td>
                        <td>${vm.ip_address}</td>
                        <td>当前: ${vm.curr_vcpu} 核 / 最大: ${vm.max_vcpu} 核 ${elasticCpu}</td>
                        <td>当前: ${Math.round(vm.curr_mem_gb)} GB / 最大: ${Math.round(vm.max_mem_gb)} GB ${elasticMemory}</td>
                        <td>${qemuGaStatus}</td>
                        <td><button class="btn btn-danger btn-sm" ${isElasticEnabled}>扩容</button></td>
                    `;

                    // 累计运行中的虚拟机资源
                    if (vm.state === 'running') {
                        totalRunningCpu += vm.curr_vcpu;
                        totalRunningMemory += Math.round(vm.curr_mem_gb);
                    }

                    tbody.appendChild(row);
                });

                // 展示总计信息
                if (totalCpuEl) totalCpuEl.textContent = totalRunningCpu;
                if (totalMemEl) totalMemEl.textContent = totalRunningMemory;

            })
            .catch(err => {
                console.error("❌ 加载失败:", err);
                tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger">加载失败: ${err.message}</td></tr>`;
            });
    }
});
