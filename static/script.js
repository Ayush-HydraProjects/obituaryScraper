/* script.js */

const entriesFetchedSpan = document.getElementById("entriesFetched");

function updateEntriesFetchedDisplay(value) {
    entriesFetchedSpan.textContent = value;
}

function startScraping() {
    if (scrapingActive) {
        alert("Scraping is already running.");
        return;
    }

    fetch('/start_scrape', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
    })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            alert(data.message);
            scrapingActive = data.scraping_active;
            updateScraperUI();
            if (data.last_scrape_time) {
                updateLastScrapeTimeDisplay(data.last_scrape_time);
            }
        })
        .catch(error => {
            console.error("Error starting scraping:", error);
            alert("Error starting scraping. Check console for details.");
        });
}

function stopScraping() {
    if (!scrapingActive) {
        alert("Scraping is not currently running.");
        return;
    }

    fetch('/stop_scrape', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
    })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            alert(data.message);
            scrapingActive = data.scraping_active;
            updateScraperUI();
            if (data.last_scrape_time) {
                updateLastScrapeTimeDisplay(data.last_scrape_time);
            }
        })
        .catch(error => {
            console.error("Error stopping scraping:", error);
            alert("Error stopping scraping. Check console for details.");
        });
}

function updateScrapingStatusDisplay() {
    fetch('/scrape_status')
        .then(response => response.json())
        .then(data => {
            scrapingActive = data.scraping_active;
            updateScraperUI();
            if (data.last_scrape_time) {
                updateLastScrapeTimeDisplay(data.last_scrape_time);
            }
        })
        .catch(error => {
            console.error("Error fetching scraping status:", error);
        });
}

function updateScraperUI() {
    if (scrapingActive) {
        document.getElementById("startButton").disabled = true;
        document.getElementById("stopButton").disabled = false;
        document.getElementById("scrapingStatus").textContent = "Scraping running...";
    } else {
        document.getElementById("startButton").disabled = false;
        document.getElementById("stopButton").disabled = true;
        document.getElementById("scrapingStatus").textContent = "Not running";
    }
}

function clearFilters() {
    document.getElementById("firstNameFilter").value = '';
    document.getElementById("lastNameFilter").value = '';
    document.getElementById("cityFilter").value = '';
    document.getElementById("provinceFilter").value = '';
    refreshObituaries();
}

document.addEventListener('DOMContentLoaded', function () {
    refreshObituaries();
    updateScrapingStatusDisplay();
    setInterval(updateScrapingStatusDisplay, 20000);
    setInterval(refreshObituaries, 100000);

    document.getElementById("filterForm").addEventListener("submit", function (event) {
        event.preventDefault();
        applyFilters();
    });

    const tagForm = document.getElementById('tagUpdateForm');
    if (tagForm) {
        tagForm.addEventListener('submit', function (e) {
            e.preventDefault();

            const formData = new FormData(this);
            const obituaryId = this.dataset.obituaryId;

            fetch(`/update_tags/${obituaryId}`, {
                method: 'POST',
                body: formData
            })
                .then(response => {
                    if (response.ok) {
                        window.location.reload();
                    } else {
                        alert('Error updating tag');
                    }
                })
                .catch(error => console.error('Error:', error));
        });
    }

    const loadMoreButton = document.getElementById('loadMoreButton');
    if (loadMoreButton) {
        loadMoreButton.addEventListener('click', loadMoreObituaries);
    }
});

let currentObituaryData = [];
let obituariesPerPage = 10;
let obituariesLoadedCount = 0;
let currentFilters = {};
let currentYearForPagination = null; // Track the year for which pagination is active

function applyFilters() {
    const firstName = document.getElementById("firstNameFilter").value.trim();
    const lastName = document.getElementById("lastNameFilter").value.trim();
    const city = document.getElementById("cityFilter").value.trim();
    const province = document.getElementById("provinceFilter").value.trim();

    currentFilters = { firstName, lastName, city, province };

    document.getElementById("loading-spinner").classList.remove("hidden");
    document.getElementById("obituaryAccordionContainer").innerHTML = "";
    document.getElementById("noNewEntries").classList.add("hidden");
    document.getElementById('loadMoreContainer').classList.add('hidden');
    obituariesLoadedCount = 0;
    currentYearForPagination = null; // Reset pagination year


    const params = new URLSearchParams();
    if (firstName) params.append("firstName", firstName);
    if (lastName) params.append("lastName", lastName);
    if (city) params.append("city", city);
    if (province) params.append("province", province);

    fetch(`/search_obituaries?${params.toString()}`)
        .then(response => response.json())
        .then(data => {
            currentObituaryData = data;
            document.getElementById("loading-spinner").classList.add("hidden");

            if (data.length === 0) {
                document.getElementById("noNewEntries").classList.remove("hidden");
            } else {
                document.getElementById("noNewEntries").classList.add("hidden");
                renderYearAccordion(getObituariesForYear("2025", 1), "2025"); // Only load 2025 initially with pagination
                renderYearAccordion(getObituariesForYear("2024", 'all'), "2024"); // Load all for 2024
                renderYearAccordion(getObituariesForYear("2023", 'all'), "2023"); // Load all for 2023
                renderYearAccordion(getObituariesForYear("2022", 'all'), "2022"); // Load all for 2022
                renderYearAccordion(getObituariesForYear("Before 2022", 'all'), "Before 2022"); // Load all before 2022
                console.log("applyFilters: After renderYearAccordion calls, calling updateLoadMoreButtonVisibility()"); // <--- ADD THIS LOG
                updateLoadMoreButtonVisibility(); // Call visibility update
            }
        })
        .catch(error => {
            console.error("Search error:", error);
            alert("Error fetching search results.");
            document.getElementById("loading-spinner").classList.add("hidden");
        });
}


function refreshObituaries() {
    document.getElementById('loading-spinner').classList.remove('hidden');
    document.getElementById('obituaryAccordionContainer').innerHTML = "";
    document.getElementById('noNewEntries').classList.add('hidden');
    document.getElementById('loadMoreContainer').classList.add('hidden');
    obituariesLoadedCount = 0;
    currentYearForPagination = null; // Reset pagination year
    currentFilters = {};

    fetch('/get_obituaries')
        .then(response => response.json())
        .then(data => {
            currentObituaryData = data;
            document.getElementById('loading-spinner').classList.add('hidden');

            if (data.length === 0) {
                document.getElementById('noNewEntries').classList.remove('hidden');
            } else {
                document.getElementById('noNewEntries').classList.add('hidden');
                renderYearAccordion(getObituariesForYear("2025", 1), "2025"); // Only load 2025 initially with pagination
                renderYearAccordion(getObituariesForYear("2024", 'all'), "2024"); // Load all for 2024
                renderYearAccordion(getObituariesForYear("2023", 'all'), "2023"); // Load all for 2023
                renderYearAccordion(getObituariesForYear("2022", 'all'), "2022"); // Load all for 2022
                renderYearAccordion(getObituariesForYear("Before 2022", 'all'), "Before 2022"); // Load all before 2022
                console.log("refreshObituaries: After renderYearAccordion calls, calling updateLoadMoreButtonVisibility()"); // <--- ADD THIS LOG
                updateLoadMoreButtonVisibility(); // Call visibility update
            }
        })
        .catch(error => {
            console.error("Error refreshing obituaries:", error);
            document.getElementById('loading-spinner').classList.add('hidden');
        });
}


function getObituariesForYear(year, pageOrAll) {
    const yearObituaries = groupObituariesByYear(currentObituaryData)[year] || [];
    console.log(`getObituariesForYear: year=${year}, pageOrAll=${pageOrAll}, yearObituaries.length=${yearObituaries.length}`);


    if (pageOrAll === 'all') {
        console.log(`  Returning ALL obituaries for ${year}`);
        return yearObituaries; // Return all obituaries for the year
    } else { // Handle page number for 2025
        const pageNumber = parseInt(pageOrAll);
        const startIndex = (pageNumber - 1) * obituariesPerPage;
        const endIndex = startIndex + obituariesPerPage;
        const pagedObituaries = yearObituaries.slice(startIndex, endIndex);
        if (year === "2025") { // Only update loaded count for 2025
            obituariesLoadedCount += pagedObituaries.length;
            currentYearForPagination = "2025"; // Set pagination year to 2025
            console.log(`  Returning page ${pageNumber} for 2025, loadedCount=${obituariesLoadedCount}`);
        } else {
            console.log(`  Returning page ${pageNumber} for ${year} (no pagination tracking)`);
        }
        return pagedObituaries;
    }
}


function loadMoreObituaries() {
    if (currentYearForPagination === "2025") { // Only load more if pagination is for 2025
        const nextPage = Math.ceil(obituariesLoadedCount / obituariesPerPage) + 1;
        const nextPageObituaries = getObituariesForYear("2025", nextPage);

        if (nextPageObituaries.length > 0) {
            renderYearAccordion(nextPageObituaries, "2025", false); // Append to 2025 accordion
        }
    }
    updateLoadMoreButtonVisibility();
}


function updateLoadMoreButtonVisibility() {
    const loadMoreContainer = document.getElementById('loadMoreContainer');
    console.log("ENTERING updateLoadMoreButtonVisibility()"); // <--- ADD THIS LOG AT THE START
    console.log(`updateLoadMoreButtonVisibility: currentYearForPagination=${currentYearForPagination}`);
    if (currentYearForPagination === "2025") { // Only consider Load More for 2025
        const total2025Obituaries = (groupObituariesByYear(currentObituaryData)["2025"] || []).length;
        console.log(`  2025: obituariesLoadedCount=${obituariesLoadedCount}, total2025Obituaries=${total2025Obituaries}`);
        if (obituariesLoadedCount < total2025Obituaries) {
            loadMoreContainer.classList.remove('hidden');
        } else {
            loadMoreContainer.classList.add('hidden');
        }
    } else { // Hide Load More for other years
        loadMoreContainer.classList.add('hidden');
    }
}


function renderYearAccordion(obituaries, year, isInitialLoad = true) { // Modified to accept year
    if (!obituaries || obituaries.length === 0) return; // Exit if no obituaries for this year

    const accordionContainer = document.getElementById('obituaryAccordionContainer');


    let yearAccordion = null;
    const accordionButtons = accordionContainer.querySelectorAll('.accordion-section .accordion-button');
    accordionButtons.forEach(button => {
        if (button.textContent.trim() === year) {
            yearAccordion = button.closest('.accordion-section');
        }
    });

    if (!yearAccordion) {
        yearAccordion = createYearAccordionSection(year, obituaries, isInitialLoad && year === "2025");
        accordionContainer.appendChild(yearAccordion);
    } else {
        if (year === "2025") { // Append only for 2025, replace for others if needed behaviour change
            const tableBody = yearAccordion.querySelector('tbody');
            if (tableBody) {
                obituaries.forEach(obituary => {
                    const row = createObituaryTableRow(obituary);
                    tableBody.appendChild(row);
                });
            }
        } else { // For other years (2024, 2023 etc.), replace content - adjust as needed
            const tableBody = yearAccordion.querySelector('tbody');
            if (tableBody) {
                tableBody.innerHTML = ''; // Clear existing content
                obituaries.forEach(obituary => {
                    const row = createObituaryTableRow(obituary);
                    tableBody.appendChild(row);
                });
            }
        }
    }

    if (isInitialLoad && year === "2025") {
        const headingButton = yearAccordion.querySelector('.accordion-button');
        if (headingButton) headingButton.classList.add('active');
    }
}


function groupObituariesByYear(obituaries) {
    const yearGroups = {
        "2025": [],
        "2024": [],
        "2023": [],
        "2022": [],
        "Before 2022": []
    };

    obituaries.forEach(obituary => {
        let publicationYear = 'Unknown Year';
        if (obituary.publication_date) {
            const year = new Date(obituary.publication_date).getFullYear();
            if (!isNaN(year)) {
                publicationYear = String(year);
            } else {
                publicationYear = 'Unknown Year';
            }
        }

        if (publicationYear === '2025') yearGroups["2025"].push(obituary);
        else if (publicationYear === '2024') yearGroups["2024"].push(obituary);
        else if (publicationYear === '2023') yearGroups["2023"].push(obituary);
        else if (publicationYear === '2022') yearGroups["2022"].push(obituary);
        else if (publicationYear !== 'Unknown Year' && parseInt(publicationYear) < 2022) yearGroups["Before 2022"].push(obituary);
    });
    return yearGroups;
}


function createYearAccordionSection(year, obituaries, isFirstSection) {
    const yearSection = document.createElement('div');
    yearSection.classList.add('accordion-section');

    const yearHeading = document.createElement('button');
    yearHeading.classList.add('accordion-button');
    yearHeading.textContent = year;
    yearHeading.addEventListener('click', () => {
        yearContent.classList.toggle('hidden');
        yearHeading.classList.toggle('active');
    });
    yearSection.appendChild(yearHeading);

    const yearContent = document.createElement('div');
    yearContent.classList.add('accordion-content');
    if (!isFirstSection) {
        yearContent.classList.add('hidden');
    }

    const obituaryTable = document.createElement('table');
    obituaryTable.classList.add('obituary-table');

    const tableHeader = document.createElement('thead');
    tableHeader.innerHTML = `
        <tr>
            <th class="border px-4 py-2">Name</th>
            <th class="border px-4 py-2">City</th>
            <th class="border px-4 py-2">Province</th>
            <th class="border px-4 py-2">Birth Date</th>
            <th class="border px-4 py-2">Death Date</th>
            <th class="border px-4 py-2">View</th>
        </tr>
    `;
    obituaryTable.appendChild(tableHeader);


    if (!obituaries || obituaries.length === 0) {
        const noObituariesPara = document.createElement('p');
        noObituariesPara.textContent = "No obituaries in this year.";
        yearContent.appendChild(noObituariesPara);
        yearSection.appendChild(yearContent);
        return yearSection;
    }


    const tableBody = document.createElement('tbody');
    obituaries.forEach(obituary => {
        const row = createObituaryTableRow(obituary);
        tableBody.appendChild(row);
    });
    obituaryTable.appendChild(tableBody);
    yearContent.appendChild(obituaryTable);
    yearSection.appendChild(yearContent);

    if (isFirstSection) {
        yearHeading.classList.add('active');
    }

    return yearSection;
}


function createObituaryTableRow(obituary) {
    const row = document.createElement('tr');
    row.classList.add("hover:bg-gray-100", "transition");

    let nameCellContent = `<td class="border px-4 py-2">`;

    if (obituary.tags === 'new') {
        nameCellContent += `
                <span class="inline-flex items-center justify-center px-2 py-1 mr-2 text-xs font-bold leading-none rounded-full primary-bg text-white">
                    New
                </span>`;
    } else if (obituary.tags === 'updated') {
        nameCellContent += `
                <span class="inline-flex items-center justify-center px-2 py-1 mr-2 text-xs font-bold leading-none rounded-full secondary-bg text-black">
                    Updated
                </span>`;
    }
    nameCellContent += `
            <a href="/obituary/${obituary.id}" class="font-medium text-gray-700 hover:text-blue-600 inline-flex items-center">
                ${obituary.first_name || 'N/A'} ${obituary.last_name || 'N/A'}
            </a></td>`;

    row.innerHTML = `
        ${nameCellContent}
        <td class="border px-4 py-2">${obituary.city || 'N/A'}</td>
        <td class="border px-4 py-2">${obituary.province || 'N/A'}</td>
        <td class="border px-4 py-2">${obituary.birth_date || 'N/A'}</td>
        <td class="border px-4 py-2">${obituary.death_date || 'N/A'}</td>
        <td class="border px-4 py-2">
            <a href="/obituary/${obituary.id}" class="text-blue-500 hover:underline">🔗 View</a>
        </td>
    `;
    return row;
}


function updateLastScrapeTimeDisplay(timeString) {
    const lastScrapeTimeSpan = document.getElementById("lastScrapeTimeDisplay");
    if (timeString) {
        lastScrapeTimeSpan.textContent = new Date(timeString).toLocaleString();
    } else {
        lastScrapeTimeSpan.textContent = "Never";
    }
}