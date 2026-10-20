from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils import timezone
from .forms import UserLoginForm, UserProfileUpdateForm


def login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            return redirect('accounts:dashboard')
        else:
            messages.error(request, "Invalid username or password. Please try again.")
    else:
        form = UserLoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('accounts:login')


@login_required
def dashboard_view(request):
    """
    Role-aware dashboard view providing key KPIs and workforce summary
    tailored to the user's role (Admin, HR, or Employee).
    """
    user = request.user
    today = timezone.now().date()
    current_year = today.year
    current_month = today.month

    context = {
        'user': user,
        'today': today,
        'current_year': current_year,
        'current_month': current_month,
    }

    # Dynamically import models to prevent circular dependencies
    from apps.employees.models import Employee, Department
    from apps.attendance.models import Attendance
    from apps.leave_management.models import LeaveRequest, LeaveBalance

    if user.is_admin_role or user.is_hr_role:
        # Admin / HR Dashboard Context
        total_employees = Employee.objects.count()
        active_employees = Employee.objects.filter(employment_status='ACTIVE').count()
        total_departments = Department.objects.filter(is_active=True).count()

        # Today's attendance numbers
        today_attendance = Attendance.objects.filter(date=today)
        present_today = today_attendance.filter(status__in=['PRESENT', 'LATE']).count()
        late_today = today_attendance.filter(status='LATE').count()
        on_leave_today = today_attendance.filter(status='ON_LEAVE').count()
        absent_today = today_attendance.filter(status='ABSENT').count()

        # Leave requests
        pending_leaves_count = LeaveRequest.objects.filter(status='PENDING').count()
        recent_leaves = LeaveRequest.objects.select_related('employee', 'leave_type').order_by('-created_at')[:5]
        recent_employees = Employee.objects.select_related('department').order_by('-joining_date')[:5]

        # Calculate average profile completeness
        employees = Employee.objects.all()
        avg_completeness = 0
        if total_employees > 0:
            total_comp = sum(emp.calculate_profile_completeness() for emp in employees)
            avg_completeness = round(total_comp / total_employees, 1)

        context.update({
            'total_employees': total_employees,
            'active_employees': active_employees,
            'total_departments': total_departments,
            'present_today': present_today,
            'late_today': late_today,
            'on_leave_today': on_leave_today,
            'absent_today': absent_today,
            'pending_leaves_count': pending_leaves_count,
            'recent_leaves': recent_leaves,
            'recent_employees': recent_employees,
            'avg_profile_completeness': avg_completeness,
        })
        return render(request, 'accounts/dashboard_admin_hr.html', context)

    else:
        # Employee Dashboard Context
        employee = getattr(user, 'employee_profile', None)
        emp_attendance_today = None
        my_leaves = []
        my_balances = []
        completeness = 0

        if employee:
            emp_attendance_today = Attendance.objects.filter(employee=employee, date=today).first()
            my_leaves = LeaveRequest.objects.filter(employee=employee).select_related('leave_type').order_by('-created_at')[:5]
            my_balances = LeaveBalance.objects.filter(employee=employee, year=current_year).select_related('leave_type')
            completeness = employee.calculate_profile_completeness()

        context.update({
            'employee': employee,
            'emp_attendance_today': emp_attendance_today,
            'my_leaves': my_leaves,
            'my_balances': my_balances,
            'profile_completeness': completeness,
        })
        return render(request, 'accounts/dashboard_employee.html', context)


@login_required
def profile_view(request):
    user = request.user
    employee = getattr(user, 'employee_profile', None)

    if request.method == 'POST':
        form = UserProfileUpdateForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile details have been updated successfully.")
            return redirect('accounts:profile')
    else:
        form = UserProfileUpdateForm(instance=user)

    return render(request, 'accounts/profile.html', {
        'form': form,
        'user': user,
        'employee': employee,
    })
