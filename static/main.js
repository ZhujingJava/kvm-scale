// 文件: static/main.js

document.addEventListener("DOMContentLoaded", function() {
    const kvmTable = document.getElementById("kvm-table");

    if (kvmTable) {
        const tbody = kvmTable.querySelector("tbody");

        // 从 body 的 data-host-ip 属性获取宿主机 IP
        const hostIp = document.body.dataset.hostIp;

        if (hostIp && hostIp !== "mock") {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center">正在加载...</td></tr>';

            // --- 修正API请求地址 ---
            fetch(`/kvm/list?host=${hostIp}`)
                .then(response => response.json())
                .then(data => {
                    tbody.innerHTML = ""; // 清空表格

                    if (data.error) {
                        tbody.innerHTML = `<tr><td colspan="5" class="text-center text-danger">加载失败: ${data.error}</td></tr>`;
                        return;
                    }

                    if (!data || data.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="5" class="text-center">该主机上没有找到虚拟机。</td></tr>';
                        return;
                    }

                    data.forEach(vm => {
                        const row = document.createElement("tr");
                        let statusBadge = (vm.state === 'running')
                            ? '<span class="badge bg-success">运行中</span>'
                            : '<span class="badge bg-secondary">已关机</span>';

                        row.innerHTML = `
                            <td>${vm.name}</td>
                            <td>${statusBadge}</td>
                            <td>${vm.vcpu}</td>
                            <td>${vm.memory_mb} MB</td>
                            <td><button class="btn btn-danger btn-sm" disabled>关机</button></td>
                        `;
                        tbody.appendChild(row);
                    });
                })
                .catch(error => {
                    console.error('Error fetching KVM data:', error);
                    tbody.innerHTML = `<tr><td colspan="5" class="text-center text-danger">网络请求失败，请检查应用日志。</td></tr>`;
                });
        }
    }
});