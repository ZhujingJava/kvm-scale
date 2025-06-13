// static/main.js

document.addEventListener("DOMContentLoaded", () => {
    // 获取服务器列表
    fetch("/api/servers")
        .then(res => res.json())
        .then(data => {
            const tbody = document.querySelector("#server-table tbody");
            data.servers.forEach(server => {
                const tr = document.createElement("tr");
                const tdIp = document.createElement("td");
                const tdAction = document.createElement("td");
                const link = document.createElement("a");

                tdIp.textContent = server.ip;
                link.textContent = "查看 KVM 列表";
                link.href = "#";
                link.onclick = () => loadKVMList(server.ip);

                tdAction.appendChild(link);
                tr.appendChild(tdIp);
                tr.appendChild(tdAction);
                tbody.appendChild(tr);
            });
        });

    function loadKVMList(ip) {
        document.getElementById("current-host").textContent = ip;
        const kvmTableBody = document.querySelector("#kvm-table tbody");
        kvmTableBody.innerHTML = "<tr><td colspan='5'>加载中...</td></tr>";

        fetch(`/api/kvm/list?host=${ip}`)
            .then(res => res.json())
            .then(data => {
                kvmTableBody.innerHTML = "";
                if (!data.vms || data.vms.length === 0) {
                    kvmTableBody.innerHTML = "<tr><td colspan='5'>无虚拟机</td></tr>";
                    return;
                }

                data.vms.forEach(vm => {
                    const tr = document.createElement("tr");
                    tr.innerHTML = `
                        <td>${vm.name}</td>
                        <td>${vm.uuid}</td>
                        <td>${vm.state}</td>
                        <td>${vm.memory}</td>
                        <td>${vm.nr_virt_cpu}</td>
                    `;
                    kvmTableBody.appendChild(tr);
                });
            })
            .catch(err => {
                kvmTableBody.innerHTML = `<tr><td colspan='5'>加载失败: ${err.message}</td></tr>`;
            });
    }
});
