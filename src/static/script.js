let authToken = '';

async function login(username, password) {
    try {
        const response = await fetch('/users/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: username,
                password: password
            })
        });

        if (response.ok) {
            const data = await response.json();
            authToken = data.token;
            console.log('Logged in, token:', authToken);
        } else {
            const errorData = await response.json();
            console.error('Login failed:', response.status, errorData);
        }
    } catch (error) {
        console.error('Error during login:', error);
    }
}

async function getUsers() {
    try {
        const response = await fetch('/users', {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        console.log('Response status:', response.status); // Log the response status
        if (!response.ok) {
            const errorBody = await response.json();
            console.error('Error fetching users:', response.status, errorBody);
            throw new Error('Network response was not ok');
        }
        const users = await response.json();
        console.log('Fetched users:', users); // Log the fetched users

        const usersDiv = document.getElementById('users');
        usersDiv.innerHTML = '';

        users.forEach(user => {
            const userDiv = document.createElement('div');
            userDiv.classList.add('user');
            userDiv.innerHTML = `
                <p><strong>ID:</strong> ${user.id}</p>
                <p><strong>Role:</strong> ${user.role}</p>
                <p><strong>Sub:</strong> ${user.sub}</p>
                ${user.avatar_url ? `<p><img src="${user.avatar_url}" alt="Avatar" style="width:100px;height:100px;"></p>` : ''}
            `;
            usersDiv.appendChild(userDiv);
        });
    } catch (error) {
        console.error('Error fetching users:', error);
    }
}

async function getCourses() {
    try {
        const response = await fetch('/courses', {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        console.log('Response status:', response.status); // Log the response status
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        const data = await response.json();
        console.log('Fetched courses:', data); // Log the fetched courses

        const coursesDiv = document.getElementById('courses');
        coursesDiv.innerHTML = '';

        data.courses.forEach(course => {
            const courseDiv = document.createElement('div');
            courseDiv.classList.add('course');
            courseDiv.dataset.id = course.id; // Set data-id attribute for the course div
            courseDiv.innerHTML = `
                <p><strong>ID:</strong> ${course.id}</p>
                <p class="subject"><strong>Subject:</strong> ${course.subject}</p>
                <p class="number"><strong>Number:</strong> ${course.number}</p>
                <p class="title"><strong>Title:</strong> ${course.title}</p>
                <p class="term"><strong>Term:</strong> ${course.term}</p>
                <p class="instructor_id"><strong>Instructor ID:</strong> ${course.instructor_id}</p>
                <button onclick="editCourseForm(${course.id})">Edit</button>
                <button onclick="deleteCourse(${course.id})">Delete</button>
            `;
            coursesDiv.appendChild(courseDiv);
        });

        if (data.next) {
            const nextButton = document.createElement('button');
            nextButton.innerText = 'Load More Courses';
            nextButton.onclick = async function() {
                const response = await fetch(data.next, {
                    headers: {
                        'Authorization': `Bearer ${authToken}`
                    }
                });
                const nextData = await response.json();
                nextData.courses.forEach(course => {
                    const courseDiv = document.createElement('div');
                    courseDiv.classList.add('course');
                    courseDiv.dataset.id = course.id; // Set data-id attribute for the course div
                    courseDiv.innerHTML = `
                        <p><strong>ID:</strong> ${course.id}</p>
                        <p class="subject"><strong>Subject:</strong> ${course.subject}</p>
                        <p class="number"><strong>Number:</strong> ${course.number}</p>
                        <p class="title"><strong>Title:</strong> ${course.title}</p>
                        <p class="term"><strong>Term:</strong> ${course.term}</p>
                        <p class="instructor_id"><strong>Instructor ID:</strong> ${course.instructor_id}</p>
                        <button onclick="editCourseForm(${course.id})">Edit</button>
                        <button onclick="deleteCourse(${course.id})">Delete</button>
                    `;
                    coursesDiv.appendChild(courseDiv);
                });
                if (nextData.next) {
                    nextButton.onclick = null;
                    nextButton.onclick = async function() {
                        await loadMoreCourses(nextData.next);
                    };
                } else {
                    nextButton.remove();
                }
            };
            coursesDiv.appendChild(nextButton);
        }
    } catch (error) {
        console.error('Error fetching courses:', error);
    }
}

async function addOrEditCourse() {
    const courseId = document.getElementById('course_id').value;
    const subject = document.getElementById('subject').value;
    const number = document.getElementById('number').value;
    const title = document.getElementById('title').value;
    const term = document.getElementById('term').value;
    const instructor_id = document.getElementById('instructor_id').value;

    const courseData = {
        subject,
        number,
        title,
        term,
        instructor_id
    };

    try {
        let response;
        if (courseId) {
            // Editing an existing course
            response = await fetch(`/courses/${courseId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify(courseData)
            });
        } else {
            // Adding a new course
            response = await fetch('/courses', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify(courseData)
            });
        }

        if (response.ok) {
            console.log('Course saved successfully');
            getCourses(); // Refresh the course list
        } else {
            const errorData = await response.json();
            console.error('Error saving course:', response.status, errorData);
        }
    } catch (error) {
        console.error('Error saving course:', error);
    }

    // Reset the form and button text
    document.getElementById('course-form').reset();
    document.getElementById('submit-btn').textContent = 'Add Course';
    document.getElementById('course-form').onsubmit = function(event) {
        event.preventDefault();
        addOrEditCourse();
    };
}

async function deleteCourse(course_id) {
    try {
        const response = await fetch(`/courses/${course_id}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });

        if (response.ok) {
            console.log('Course deleted successfully');
            getCourses(); // Refresh the course list
        } else {
            const errorData = await response.json();
            console.error('Error deleting course:', response.status, errorData);
        }
    } catch (error) {
        console.error('Error deleting course:', error);
    }
}

function editCourseForm(course_id) {
    // Pre-fill the form with existing course data
    const courseDiv = document.querySelector(`.course[data-id='${course_id}']`);
    document.getElementById('subject').value = courseDiv.querySelector('.subject').textContent;
    document.getElementById('number').value = courseDiv.querySelector('.number').textContent;
    document.getElementById('title').value = courseDiv.querySelector('.title').textContent;
    document.getElementById('term').value = courseDiv.querySelector('.term').textContent;
    document.getElementById('instructor_id').value = courseDiv.querySelector('.instructor_id').textContent;
    document.getElementById('course_id').value = course_id;

    // Change the form's submit button to update the course instead of adding a new one
    document.getElementById('submit-btn').textContent = 'Update Course';
    document.getElementById('course-form').onsubmit = function(event) {
        event.preventDefault();
        addOrEditCourse();
    };
}

document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('load-users').addEventListener('click', function() {
        getUsers();
    });

    document.getElementById('load-courses').addEventListener('click', function() {
        getCourses();
    });

    document.getElementById('login-btn').addEventListener('click', function() {
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        login(username, password);
    });

    document.getElementById('course-form').addEventListener('submit', function(event) {
        event.preventDefault();
        addOrEditCourse();
    });
});
