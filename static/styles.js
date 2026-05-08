// Mobile Menu Toggle
const mobileMenuBtn = document.getElementById('mobileMenuBtn');
const navLinks = document.getElementById('navLinks');

mobileMenuBtn.addEventListener('click', () => {
    navLinks.classList.toggle('active');
    mobileMenuBtn.textContent = navLinks.classList.contains('active') ? '✕' : '☰';
});

// Close mobile menu when clicking a link
document.querySelectorAll('.nav-links a').forEach(link => {
    link.addEventListener('click', () => {
        navLinks.classList.remove('active');
        mobileMenuBtn.textContent = '☰';
    });
});

// Announcements Auto-Slider
const announcementSlides = document.querySelectorAll('.announcement-slide');
let currentAnnouncement = 0;
let announcementInterval;

function showAnnouncement(n) {
    announcementSlides[currentAnnouncement].classList.remove('active');
    if (announcementDots[currentAnnouncement]) announcementDots[currentAnnouncement].classList.remove('active');

    currentAnnouncement = n;
    if (currentAnnouncement >= announcementSlides.length) currentAnnouncement = 0;
    if (currentAnnouncement < 0) currentAnnouncement = announcementSlides.length - 1;

    announcementSlides[currentAnnouncement].classList.add('active');
    if (announcementDots[currentAnnouncement]) announcementDots[currentAnnouncement].classList.add('active');
}

function nextAnnouncement() {
    showAnnouncement(currentAnnouncement + 1);
}

function stopAnnouncementSlider() {
    clearInterval(announcementInterval);
}

function startAnnouncementSlider() {
    stopAnnouncementSlider();
    announcementInterval = setInterval(nextAnnouncement, 5000);
}

// Announcement dots - initialize before starting slider
const announcementDotsContainer = document.getElementById('announcementDots');
let announcementDots = [];
if (announcementDotsContainer) {
    announcementSlides.forEach((_, index) => {
        const dot = document.createElement('div');
        dot.classList.add('dot');
        if (index === 0) dot.classList.add('active');
        dot.addEventListener('click', () => {
            showAnnouncement(index);
            startAnnouncementSlider();
        });
        announcementDotsContainer.appendChild(dot);
    });
    announcementDots = announcementDotsContainer.querySelectorAll('.dot');
}

startAnnouncementSlider();

const announcementsSliderEl = document.querySelector('.announcements-slider');
if (announcementsSliderEl) {
    announcementsSliderEl.addEventListener('mouseenter', stopAnnouncementSlider);
    announcementsSliderEl.addEventListener('mouseleave', startAnnouncementSlider);
}

// Smooth scrolling
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// ===========================
// PROGRESSIVE BOOKING FORM
// ===========================

// Services data structure
const servicesData = {
    'Nail Services': [
        { name: 'Gel polish', price: 180 },
        { name: 'Gel removal', price: 50 },
        { name: 'Acrylic', price: 350 },
        { name: 'Acrylic removal', price: 100 },
        { name: 'Soak off refill', price: 250 },
        { name: 'Acrylic refill', price: 300 },
        { name: 'Gel polish & P/S', price: 300 },
        { name: 'Pedicure', price: 150 },
        { name: 'Manicure', price: 100 },
        { name: 'Express pedi', price: 80 },
        { name: 'Polish change hands', price: 50 },
        { name: 'Polish change feet', price: 80 }
    ],
    'Massage Therapy': [
        { name: 'Back massage', price: 200 },
        { name: 'Full body massage', price: 400 },
        { name: 'Head massage', price: 150 },
        { name: 'Hot stone massage', price: 700 },
        { name: 'Hot oil foot massage', price: 150 }
    ],
    'Body Treatments': [
        { name: 'Body polishing', price: 400 },
        { name: 'Spot treatment', price: 300 },
        { name: 'Back treatment', price: 450 },
        { name: 'Body wrap', price: 450 },
        { name: 'Steaming', price: 200 }
    ],
    'Facial Treatments': [
        { name: 'Back facial', price: 450 },
        { name: 'Deep cleansing facial', price: 400 },
        { name: 'Anti-aging', price: 500 },
        { name: 'Blemish control', price: 400 },
        { name: 'Hydro-quench', price: 400 },
        { name: 'Brightening facial', price: 450 },
        { name: 'Glycolic peel', price: 350 },
        { name: 'Express facial', price: 300 },
        { name: 'Diamond polish', price: 350 }
    ],
    'Waxing': [
        { name: 'Eyebrow threading', price: 50 },
        { name: 'Upper lip', price: 50 },
        { name: 'Chin', price: 80 },
        { name: 'Full face', price: 200 },
        { name: 'Underarms', price: 100 },
        { name: 'Full arms', price: 300 },
        { name: 'Half leg', price: 250 },
        { name: 'Full leg', price: 400 },
        { name: 'Full leg & bikini', price: 500 },
        { name: 'Bikini', price: 120 },
        { name: 'Brazilian', price: 200 },
        { name: 'Hollywood', price: 300 },
        { name: 'Chest', price: 200 },
        { name: 'Full back', price: 350 }
    ],
    'Laser Treatments': [
        { name: 'Upper lip', price: 150 },
        { name: 'Chin', price: 250 },
        { name: 'Neck', price: 350 },
        { name: 'Lower face', price: 500 },
        { name: 'Full face', price: 600 },
        { name: 'Chest', price: 500 },
        { name: 'Tummy line', price: 300 },
        { name: 'Full tummy', price: 600 },
        { name: 'Underarms', price: 500 },
        { name: 'Full arms', price: 900 },
        { name: 'Full back', price: 1000 },
        { name: 'Brazilian', price: 500 },
        { name: 'Hollywood', price: 680 },
        { name: 'Buttocks', price: 600 },
        { name: 'Half leg', price: 800 },
        { name: 'Full leg', price: 1400 }
    ]
};

// Booking state
let bookingData = {
    services: [],
    date: '',
    time: '',
    name: '',
    email: '',
    phone: '',
    notes: '',
    paymentMethod: 'at-spa'
};

let currentStep = 1;
const totalSteps = 6;

// Initialize booking form
function initBookingForm() {
    loadServices();
    loadTimeSlots();
    setupEventListeners();
}

// Load services into step 1
function loadServices() {
    const serviceSelection = document.getElementById('serviceSelection');
    if (!serviceSelection) return;

    serviceSelection.innerHTML = '';

    Object.keys(servicesData).forEach(category => {
        const categoryDiv = document.createElement('div');
        categoryDiv.className = 'service-category-selector';

        const categoryHeader = document.createElement('div');
        categoryHeader.className = 'category-header';
        categoryHeader.innerHTML = `
            <h5>${category}</h5>
            <span class="category-icon">▼</span>
        `;

        const servicesDiv = document.createElement('div');
        servicesDiv.className = 'category-services';

        servicesData[category].forEach((service, index) => {
            const serviceItem = document.createElement('div');
            serviceItem.className = 'service-checkbox-item';
            const serviceId = `service-${category.replace(/\s+/g, '-')}-${index}`;

            serviceItem.innerHTML = `
                <input type="checkbox" id="${serviceId}" value="${service.name}" data-price="${service.price}" data-category="${category}">
                <label for="${serviceId}" class="service-checkbox-label">${service.name}</label>
                <span class="service-checkbox-price">K${service.price}</span>
            `;

            servicesDiv.appendChild(serviceItem);
        });

        categoryDiv.appendChild(categoryHeader);
        categoryDiv.appendChild(servicesDiv);
        serviceSelection.appendChild(categoryDiv);

        // Toggle category
        categoryHeader.addEventListener('click', () => {
            categoryHeader.classList.toggle('active');
            servicesDiv.classList.toggle('active');
        });
    });

    // Add service selection change listeners
    document.querySelectorAll('#serviceSelection input[type="checkbox"]').forEach(checkbox => {
        checkbox.addEventListener('change', updateSelectedServices);
    });
}

// Update selected services summary
function updateSelectedServices() {
    const selectedCheckboxes = document.querySelectorAll('#serviceSelection input[type="checkbox"]:checked');
    const summary = document.getElementById('selectedServicesSummary');
    const list = document.getElementById('selectedServicesList');
    const totalElement = document.getElementById('totalPrice');

    bookingData.services = [];
    let total = 0;

    list.innerHTML = '';

    selectedCheckboxes.forEach(checkbox => {
        const service = {
            name: checkbox.value,
            price: parseInt(checkbox.dataset.price),
            category: checkbox.dataset.category
        };
        bookingData.services.push(service);
        total += service.price;

        const item = document.createElement('div');
        item.className = 'selected-service-item';
        item.innerHTML = `
            <span>${service.name}</span>
            <span>K${service.price}</span>
        `;
        list.appendChild(item);
    });

    if (bookingData.services.length > 0) {
        summary.style.display = 'block';
        totalElement.textContent = total;
    } else {
        summary.style.display = 'none';
    }
}

// Load time slots
function loadTimeSlots() {
    const timeSlotsContainer = document.getElementById('timeSlots');
    if (!timeSlotsContainer) return;

    const timeSlots = [
        '9:00 AM', '9:30 AM', '10:00 AM', '10:30 AM', '11:00 AM', '11:30 AM',
        '12:00 PM', '12:30 PM', '1:00 PM', '1:30 PM', '2:00 PM', '2:30 PM',
        '3:00 PM', '3:30 PM', '4:00 PM', '4:30 PM', '5:00 PM', '5:30 PM',
        '6:00 PM', '6:30 PM'
    ];

    timeSlotsContainer.innerHTML = '';

    timeSlots.forEach(time => {
        const slot = document.createElement('div');
        slot.className = 'time-slot';
        slot.textContent = time;
        slot.addEventListener('click', () => selectTimeSlot(slot, time));
        timeSlotsContainer.appendChild(slot);
    });
}

// Select time slot
function selectTimeSlot(element, time) {
    if (element.classList.contains('unavailable')) return;

    document.querySelectorAll('.time-slot').forEach(slot => {
        slot.classList.remove('selected');
    });

    element.classList.add('selected');
    bookingData.time = time;
}

// Setup event listeners
function setupEventListeners() {
    // Date change
    const dateInput = document.getElementById('appointmentDate');
    if (dateInput) {
        // Set minimum date to today
        const today = new Date().toISOString().split('T')[0];
        dateInput.setAttribute('min', today);

        dateInput.addEventListener('change', (e) => {
            bookingData.date = e.target.value;
        });
    }

    // Form inputs
    const nameInput = document.getElementById('fullName');
    const emailInput = document.getElementById('emailAddress');
    const phoneInput = document.getElementById('phoneNumber');
    const notesInput = document.getElementById('additionalNotes');

    if (nameInput) nameInput.addEventListener('input', (e) => bookingData.name = e.target.value);
    if (emailInput) emailInput.addEventListener('input', (e) => bookingData.email = e.target.value);
    if (phoneInput) phoneInput.addEventListener('input', (e) => bookingData.phone = e.target.value);
    if (notesInput) notesInput.addEventListener('input', (e) => bookingData.notes = e.target.value);

    // Payment method
    document.querySelectorAll('input[name="paymentMethod"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            bookingData.paymentMethod = e.target.value;
            showPaymentInstructions(e.target.value);
        });
    });

    // Form submission
    const form = document.getElementById('bookingForm');
    if (form) {
        form.addEventListener('submit', handleFormSubmit);
    }
}

// Show payment instructions
function showPaymentInstructions(method) {
    const instructionsDiv = document.getElementById('paymentInstructions');
    if (!instructionsDiv) return;

    let instructions = '';

    switch (method) {
        case 'mobile-money':
            instructions = `
                <h5>Mobile Money Payment</h5>
                <p>Please send your payment to:</p>
                <p><strong>MTN:</strong> 0973 407 110</p>
                <p><strong>Airtel:</strong> 0973 407 110</p>
                <p>Reference: Your name</p>
            `;
            break;
        case 'bank-transfer':
            instructions = `
                <h5>Bank Transfer Details</h5>
                <p><strong>Bank:</strong> Example Bank</p>
                <p><strong>Account Name:</strong> Skin Sensation Spa</p>
                <p><strong>Account Number:</strong> 1234567890</p>
                <p>Please send proof of payment to our email.</p>
            `;
            break;
        case 'at-spa':
            instructions = `
                <h5>Pay at Spa</h5>
                <p>You can pay when you arrive for your appointment.</p>
                <p>We accept cash, mobile money, and card payments.</p>
            `;
            break;
    }

    if (instructions) {
        instructionsDiv.innerHTML = instructions;
        instructionsDiv.style.display = 'block';
    } else {
        instructionsDiv.style.display = 'none';
    }
}

// Change step
function changeStep(direction) {
    // Validate current step before proceeding
    if (direction > 0 && !validateStep(currentStep)) {
        return;
    }

    const newStep = currentStep + direction;

    if (newStep < 1 || newStep > totalSteps) return;

    // Update step content
    document.querySelectorAll('.form-step').forEach(step => {
        step.classList.remove('active');
    });

    document.querySelector(`[data-step="${newStep}"]`).classList.add('active');

    // Update progress indicator
    updateProgressIndicator(newStep);

    // Update buttons
    updateNavigationButtons(newStep);

    // If moving to review step, populate review
    if (newStep === 4) {
        populateReview();
    }

    // If moving to confirmation step, show booking reference
    if (newStep === 6) {
        showConfirmation();
    }

    currentStep = newStep;

    // Scroll to top of form
    document.getElementById('contact').scrollIntoView({ behavior: 'smooth' });
}

// Validate step
function validateStep(step) {
    switch (step) {
        case 1:
            if (bookingData.services.length === 0) {
                alert('Please select at least one service.');
                return false;
            }
            return true;
        case 2:
            if (!bookingData.date) {
                alert('Please select a date.');
                return false;
            }
            if (!bookingData.time) {
                alert('Please select a time slot.');
                return false;
            }
            return true;
        case 3:
            if (!bookingData.name || !bookingData.email || !bookingData.phone) {
                alert('Please fill in all required fields.');
                return false;
            }
            // Basic email validation
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(bookingData.email)) {
                alert('Please enter a valid email address.');
                return false;
            }
            return true;
        case 4:
            return true;
        case 5:
            return true;
        default:
            return true;
    }
}

// Update progress indicator
function updateProgressIndicator(step) {
    document.querySelectorAll('.progress-step').forEach((progressStep, index) => {
        const stepNumber = index + 1;

        if (stepNumber < step) {
            progressStep.classList.add('completed');
            progressStep.classList.remove('active');
        } else if (stepNumber === step) {
            progressStep.classList.add('active');
            progressStep.classList.remove('completed');
        } else {
            progressStep.classList.remove('active');
            progressStep.classList.remove('completed');
        }
    });
}

// Update navigation buttons
function updateNavigationButtons(step) {
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const submitBtn = document.getElementById('submitBtn');

    // Show/hide previous button
    if (step === 1 || step === 6) {
        prevBtn.style.display = 'none';
    } else {
        prevBtn.style.display = 'inline-block';
    }

    // Show/hide next vs submit button
    if (step === 5) {
        nextBtn.style.display = 'none';
        submitBtn.style.display = 'inline-block';
    } else if (step === 6) {
        nextBtn.style.display = 'none';
        submitBtn.style.display = 'none';
    } else {
        nextBtn.style.display = 'inline-block';
        submitBtn.style.display = 'none';
    }
}

// Populate review
function populateReview() {
    const reviewServices = document.getElementById('reviewServices');
    const reviewDateTime = document.getElementById('reviewDateTime');
    const reviewContact = document.getElementById('reviewContact');
    const reviewTotal = document.getElementById('reviewTotal');

    // Services
    let servicesHTML = '<div class="review-item">';
    let total = 0;
    bookingData.services.forEach(service => {
        servicesHTML += `<p>${service.name} - K${service.price}</p>`;
        total += service.price;
    });
    servicesHTML += '</div>';
    reviewServices.innerHTML = servicesHTML;

    // Date & Time
    const [year, month, day] = bookingData.date.split('-');
    const dateObj = new Date(year, month - 1, day);
    const formattedDate = dateObj.toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
    reviewDateTime.innerHTML = `
        <div class="review-item">
            <p><strong>Date:</strong> ${formattedDate}</p>
            <p><strong>Time:</strong> ${bookingData.time}</p>
        </div>
    `;

    // Contact
    reviewContact.innerHTML = `
        <div class="review-item">
            <p><strong>Name:</strong> ${bookingData.name}</p>
            <p><strong>Email:</strong> ${bookingData.email}</p>
            <p><strong>Phone:</strong> ${bookingData.phone}</p>
            ${bookingData.notes ? `<p><strong>Notes:</strong> ${bookingData.notes}</p>` : ''}
        </div>
    `;

    // Total
    reviewTotal.textContent = total;
}

// Handle form submission
function handleFormSubmit(e) {
    e.preventDefault();

    // In a real application, you would send this data to a backend
    console.log('Booking Data:', bookingData);

    // Move to confirmation step
    changeStep(1);
}

// Show confirmation
function showConfirmation() {
    // Generate a random booking reference
    const reference = 'SSS-' + Math.random().toString(36).substr(2, 9).toUpperCase();
    document.getElementById('bookingReference').textContent = reference;
    document.getElementById('confirmEmail').textContent = bookingData.email;
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    initBookingForm();
    // Initialize payment instructions
    showPaymentInstructions('at-spa');
});