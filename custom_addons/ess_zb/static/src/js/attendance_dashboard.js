/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class AttendanceDashboard extends Component {
  setup() {
    this.orm = useService("orm");
    this.notification = useService("notification");
    this.state = useState({
      employeeName: "",
      isCheckedIn: false,
      checkInTime: "",
      loading: false,
    });

    onMounted(() => {
      this.loadAttendanceStatus();
    });
  }

  async loadAttendanceStatus() {
    try {
      const result = await this.orm.call(
        "hr.attendance",
        "get_employee_attendance_status",
        []
      );
      if (result.error) {
        this.notification.add(result.error, { type: "danger" });
        return;
      }

      this.state.employeeName = result.employee_name;
      this.state.isCheckedIn = result.is_checked_in;
      this.state.checkInTime = result.check_in_time;
    } catch (error) {
      console.error("Error loading attendance:", error);
      this.notification.add("Failed to load attendance status", {
        type: "danger",
      });
    }
  }

  async getLocation() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error("Geolocation is not supported by your browser"));
        return;
      }

      navigator.geolocation.getCurrentPosition(
        (position) => {
          resolve({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          });
        },
        (error) => {
          let errorMsg = "Unable to get location. ";
          switch (error.code) {
            case error.PERMISSION_DENIED:
              errorMsg += "Please allow location access.";
              break;
            case error.POSITION_UNAVAILABLE:
              errorMsg += "Location information unavailable.";
              break;
            case error.TIMEOUT:
              errorMsg += "Location request timed out.";
              break;
            default:
              errorMsg += error.message;
          }
          reject(new Error(errorMsg));
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 0,
        }
      );
    });
  }

  async checkIn() {
    this.state.loading = true;
    try {
      const location = await this.getLocation();
      const result = await this.orm.call(
        "hr.attendance",
        "employee_check_in",
        [],
        {
          latitude: location.latitude,
          longitude: location.longitude,
        }
      );
      this.notification.add("Checked in successfully!", { type: "success" });
      await this.loadAttendanceStatus();
    } catch (error) {
      console.error("Check-in error:", error);
      // Extract actual error message from RPC error
      let errorMessage = "Check-in failed";
      if (error.data && error.data.message) {
        errorMessage = error.data.message;
      } else if (error.message) {
        errorMessage = error.message;
      }
      this.notification.add(errorMessage, {
        type: "danger",
        sticky: true,
      });
    } finally {
      this.state.loading = false;
    }
  }

  async checkOut() {
    this.state.loading = true;
    try {
      const location = await this.getLocation();
      const result = await this.orm.call(
        "hr.attendance",
        "employee_check_out",
        [],
        {
          latitude: location.latitude,
          longitude: location.longitude,
        }
      );
      this.notification.add("Checked out successfully!", { type: "success" });
      await this.loadAttendanceStatus();
    } catch (error) {
      console.error("Check-out error:", error);
      let errorMessage = "Check-out failed";
      if (error.data && error.data.message) {
        errorMessage = error.data.message;
      } else if (error.message) {
        errorMessage = error.message;
      }
      this.notification.add(errorMessage, {
        type: "danger",
        sticky: true,
      });
    } finally {
      this.state.loading = false;
    }
  }
}

AttendanceDashboard.template = "ess_zb.AttendanceDashboard";

registry.category("actions").add("attendance_dashboard", AttendanceDashboard);
