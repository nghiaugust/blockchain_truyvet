// Tạo và thêm các phần tử sidebar vào DOM
function createSidebar() {
  // Tạo container chính
  const sidebarContainer = document.createElement('div');
  sidebarContainer.className = 'sidebar-container';

  // Tạo nút toggle
  const sidebarToggle = document.createElement('div');
  sidebarToggle.className = 'sidebar-toggle';
  sidebarToggle.id = 'sidebarToggle';
  sidebarToggle.innerHTML = '<i class="bi bi-list"></i> Menu';
  
  // Tạo sidebar chính
  const sidebar = document.createElement('div');
  sidebar.className = 'sidebar';
  sidebar.id = 'sidebar';

  // Tạo header của sidebar
  const sidebarHeader = document.createElement('div');
  sidebarHeader.className = 'sidebar-header';
  sidebarHeader.innerHTML = '<h5>Bitcoin Explorer</h5>' + 
                           '<button class="btn-close text-reset" id="closeSidebar" aria-label="Close"></button>';

  // Tạo phần thân sidebar với các liên kết
  const sidebarBody = document.createElement('div');
  sidebarBody.className = 'sidebar-body';

  // Menu chính
  const navList = document.createElement('ul');
  navList.className = 'nav flex-column';

  const baseUrl = window.location.origin; // Lấy gốc của URL hiện tại (http://localhost:8000)

  // Tạo các mục menu
  const menuItems = [
    { url: baseUrl + '/graph/', icon: 'bi-search', text: 'Truy vấn theo Địa chỉ' },
    { url: baseUrl + '/tx_graph/', icon: 'bi-currency-bitcoin', text: 'Truy vấn theo Giao dịch' },
    { url: baseUrl + '/cluster_graph/', icon: 'bi-diagram-3', text: 'Truy vấn theo Cụm' },
    { separator: true },
    { url: '#', icon: 'bi-info-circle', text: 'Giới thiệu' },
    { url: '#', icon: 'bi-question-circle', text: 'Trợ giúp' }
  ];

  // Tạo các mục menu
  menuItems.forEach(item => {
    if (item.separator) {
      const separator = document.createElement('li');
      separator.className = 'nav-item separator';
      navList.appendChild(separator);
      return;
    }

    const menuItem = document.createElement('li');
    menuItem.className = 'nav-item';
    
    const link = document.createElement('a');
    link.className = 'nav-link';
    link.href = item.url;
    link.innerHTML = `<i class="bi ${item.icon} me-2"></i>${item.text}`;
    
    menuItem.appendChild(link);
    navList.appendChild(menuItem);
  });

  // Tạo overlay
  const overlay = document.createElement('div');
  overlay.className = 'sidebar-overlay';
  overlay.id = 'sidebarOverlay';

  // Ghép các phần lại với nhau
  sidebarBody.appendChild(navList);
  sidebar.appendChild(sidebarHeader);
  sidebar.appendChild(sidebarBody);
  sidebarContainer.appendChild(sidebarToggle);
  sidebarContainer.appendChild(sidebar);
  
  // Thêm vào đầu body
  document.body.insertBefore(sidebarContainer, document.body.firstChild);
  document.body.appendChild(overlay);

  // Thêm CSS
  addSidebarStyles();
  
  // Thêm các event listeners
  initializeSidebarBehavior();
}

// Thêm CSS cho sidebar
function addSidebarStyles() {
  const style = document.createElement('style');
  style.textContent = `
    .sidebar-container {
      position: relative;
      z-index: 1030;
    }

    .sidebar {
      position: fixed;
      top: 0;
      left: -280px;
      width: 280px;
      height: 100%;
      background-color: #343a40;
      color: #fff;
      overflow-y: auto;
      transition: left 0.3s ease;
      z-index: 1040;
      box-shadow: 3px 0 5px rgba(0, 0, 0, 0.2);
    }

    .sidebar.active {
      left: 0;
    }

    .sidebar-header {
      padding: 15px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      background-color: #212529;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }

    .sidebar-body {
      padding: 15px 0;
    }

    .sidebar-toggle {
      position: fixed;
      top: 20px;
      left: 20px;
      background-color: #212529;
      color: #fff;
      padding: 10px 15px;
      border-radius: 4px;
      cursor: pointer;
      z-index: 1030;
      transition: all 0.3s ease;
      box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
    }

    .sidebar-toggle:hover {
      background-color: #0d6efd;
    }

    .sidebar-overlay {
      display: none;
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background-color: rgba(0, 0, 0, 0.4);
      z-index: 1035;
    }

    .sidebar .nav-link {
      color: rgba(255, 255, 255, 0.8);
      padding: 10px 20px;
      transition: all 0.2s;
    }

    .sidebar .nav-link:hover,
    .sidebar .nav-link.active {
      color: #fff;
      background-color: #0d6efd;
    }

    .sidebar .separator {
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
      margin: 10px 15px;
    }

    /* Điều chỉnh nội dung chính khi sidebar hoạt động */
    .main-content {
      transition: margin-left 0.3s ease;
    }

    .main-content.active {
      margin-left: 280px;
    }

    /* Responsive */
    @media (max-width: 768px) {
      .main-content.active {
        margin-left: 0;
      }
    }
  `;
  
  document.head.appendChild(style);
}

// Thêm các event listeners cho sidebar
function initializeSidebarBehavior() {
  const sidebar = document.getElementById("sidebar");
  const sidebarToggle = document.getElementById("sidebarToggle");
  const closeSidebar = document.getElementById("closeSidebar");
  const sidebarOverlay = document.getElementById("sidebarOverlay");
  const mainContent = document.querySelector(".container-fluid");

  function openSidebar() {
    sidebar.classList.add("active");
    sidebarOverlay.style.display = "block";

    // Trên màn hình lớn, đẩy nội dung sang phải
    if (window.innerWidth > 768) {
      mainContent.classList.add("active");
    }
  }

  function closeSidebarFunc() {
    sidebar.classList.remove("active");
    sidebarOverlay.style.display = "none";
    mainContent.classList.remove("active");
  }

  sidebarToggle.addEventListener("click", openSidebar);
  closeSidebar.addEventListener("click", closeSidebarFunc);
  sidebarOverlay.addEventListener("click", closeSidebarFunc);

  // Đánh dấu trang hiện tại
  const currentPath = window.location.pathname;
  const navLinks = document.querySelectorAll(".sidebar .nav-link");

  navLinks.forEach((link) => {
    const href = link.getAttribute("href");
    // Kiểm tra nếu URL hiện tại kết thúc bằng href của liên kết
    if (href !== '#' && currentPath.endsWith(href.split('/').filter(Boolean).pop() + '/')) {
      link.classList.add("active");
    }
  });
}

// Xử lý sự kiện click cho các liên kết sidebar sau khi trang đã tải
function setupSidebarLinks() {
  document.querySelectorAll('.sidebar .nav-link').forEach(function(link) {
    link.addEventListener('click', function() {
      // Đảm bảo điều hướng hoạt động bình thường (không chặn hành vi mặc định)
      // Trên thiết bị di động, đóng sidebar sau khi click
      if (window.innerWidth <= 768) {
        const sidebar = document.getElementById('sidebar');
        const sidebarOverlay = document.getElementById('sidebarOverlay');
        if (sidebar) {
          // Đóng sidebar sau một khoảng thời gian ngắn để điều hướng hoạt động trước
          setTimeout(function() {
            sidebar.classList.remove('active');
            if (sidebarOverlay) sidebarOverlay.style.display = 'none';
            const mainContent = document.querySelector('.container-fluid');
            if (mainContent) mainContent.classList.remove('active');
          }, 50);
        }
      }
    });
  });
}

// Thực hiện tạo sidebar và thiết lập sự kiện khi DOM đã tải xong
document.addEventListener("DOMContentLoaded", function() {
  createSidebar();
  // Thiết lập các sự kiện sau một khoảng thời gian ngắn để đảm bảo DOM đã được cập nhật
  setTimeout(setupSidebarLinks, 100);
});
