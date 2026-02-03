/* =========================================
   Main JavaScript Application Logic
   ========================================= */

/**
 * Toggles the sidebar visibility on mobile devices
 */
function toggleSidebar() {
  const sidebar = document.getElementById("sidebar");
  if (sidebar) {
    sidebar.classList.toggle("show");
  }
}

/**
 * Handles the login redirection for index.html
 * @param {Event} event
 */
function redirectToDashboard(event) {
  // Prevents the page from refreshing or sending data to a server
  event.preventDefault();

  // Instant redirect to your main dashboard page
  window.location.href = "dashboard.html";
}

// Initialize event listeners when the DOM is fully loaded
document.addEventListener("DOMContentLoaded", function () {
  // Staff Management Form Handler (staff.html)
  const addStaffForm = document.getElementById("addStaffForm");
  if (addStaffForm) {
    addStaffForm.addEventListener("submit", function (e) {
      e.preventDefault();

      // Get values
      const name = document.getElementById("staffName").value;
      const email = document.getElementById("staffEmail").value;
      const id = document.getElementById("staffID").value;
      const role = document.getElementById("staffRole").value;

      // Create new row
      const table = document
        .getElementById("staffTable")
        .getElementsByTagName("tbody")[0];
      const newRow = table.insertRow();

      newRow.innerHTML = `
                <td class="px-4">
                    <div class="d-flex align-items-center gap-3">
                        <img src="https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&background=random" class="rounded-circle" width="36">
                        <div>
                            <p class="mb-0 small fw-bold">${name}</p>
                            <small class="text-muted">${email}</small>
                        </div>
                    </div>
                </td>
                <td class="small fw-medium">${id}</td>
                <td><span class="badge-role bg-light text-muted">${role}</span></td>
                <td><span class="status-dot bg-success me-1"></span> <small class="fw-medium">Active</small></td>
                <td class="small fw-bold text-muted">0</td>
                <td class="px-4 text-end">
                    <button class="btn btn-sm btn-light text-muted border"><i class="bi bi-pencil"></i></button>
                    <button class="btn btn-sm btn-light text-danger border"><i class="bi bi-slash-circle"></i></button>
                </td>
            `;

      // Close Modal
      // Assumes bootstrap is available globally as it is loaded via script tag
      if (typeof bootstrap !== "undefined") {
        const modal = bootstrap.Modal.getInstance(
          document.getElementById("addStaffModal"),
        );
        if (modal) {
          modal.hide();
        }
      }

      // Reset Form
      addStaffForm.reset();

      alert("Staff member added successfully!");
    });
  }
});
