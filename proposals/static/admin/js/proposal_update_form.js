document.addEventListener("DOMContentLoaded", function () {
    const clientSelect = document.getElementById("id_client");
    const proposalSelect = document.getElementById("id_proposal");
    const milestoneSelect = document.getElementById("id_milestone");

    if (!clientSelect || !proposalSelect || !milestoneSelect) {
        console.error("Proposal update form fields not found.", {
            clientSelect,
            proposalSelect,
            milestoneSelect,
        });
        return;
    }

    const originalProposalId = proposalSelect.value;
    const originalMilestoneId = milestoneSelect.value;

    function resetProposals(message = "---------") {
        proposalSelect.innerHTML = "";

        const option = document.createElement("option");
        option.value = "";
        option.textContent = message;

        proposalSelect.appendChild(option);
        proposalSelect.disabled = true;
    }

    function resetMilestones(message = "---------") {
        milestoneSelect.innerHTML = "";

        const option = document.createElement("option");
        option.value = "";
        option.textContent = message;

        milestoneSelect.appendChild(option);
        milestoneSelect.disabled = true;
    }

    async function loadProposals(clientId, selectedProposalId = "") {
        resetProposals("Loading proposals...");
        resetMilestones();

        if (!clientId) {
            resetProposals();
            return;
        }

        try {
            /*
             * Django admin model URL:
             *
             * /admin/proposals/proposalupdate/add/
             * /admin/proposals/proposalupdate/<id>/change/
             *
             * We remove the final add/change section and append
             * our custom admin endpoint.
             */

            let path = window.location.pathname;

            path = path.replace(/\/add\/$/, "/");
            path = path.replace(/\/[^/]+\/change\/$/, "/");

            if (!path.endsWith("/")) {
                path += "/";
            }

            const url =
                path +
                "client-proposals/?client_id=" +
                encodeURIComponent(clientId);

            console.log("Loading proposals from:", url);

            const response = await fetch(url, {
                method: "GET",
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json",
                },
            });

            if (!response.ok) {
                throw new Error(
                    `HTTP ${response.status}: ${response.statusText}`
                );
            }

            const data = await response.json();

            proposalSelect.innerHTML =
                '<option value="">---------</option>';

            const proposals = Array.isArray(data.proposals)
                ? data.proposals
                : [];

            proposals.forEach(function (proposal) {
                const option = document.createElement("option");

                option.value = proposal.id;

                option.textContent =
                    proposal.title +
                    " — " +
                    proposal.status;

                if (
                    selectedProposalId &&
                    String(proposal.id) ===
                    String(selectedProposalId)
                ) {
                    option.selected = true;
                }

                proposalSelect.appendChild(option);
            });

            proposalSelect.disabled = false;

            if (selectedProposalId) {
                await loadMilestones(
                    selectedProposalId,
                    originalMilestoneId
                );
            }

        } catch (error) {
            console.error(
                "Unable to load proposals:",
                error
            );

            proposalSelect.innerHTML =
                '<option value="">Unable to load proposals</option>';

            proposalSelect.disabled = true;
        }
    }

    async function loadMilestones(
        proposalId,
        selectedMilestoneId = ""
    ) {
        resetMilestones("Loading milestones...");

        if (!proposalId) {
            resetMilestones();
            return;
        }

        try {
            let path = window.location.pathname;

            path = path.replace(/\/add\/$/, "/");
            path = path.replace(/\/[^/]+\/change\/$/, "/");

            if (!path.endsWith("/")) {
                path += "/";
            }

            const url =
                path +
                "proposal-milestones/?proposal_id=" +
                encodeURIComponent(proposalId);

            console.log("Loading milestones from:", url);

            const response = await fetch(url, {
                method: "GET",
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json",
                },
            });

            if (!response.ok) {
                throw new Error(
                    `HTTP ${response.status}: ${response.statusText}`
                );
            }

            const data = await response.json();

            milestoneSelect.innerHTML =
                '<option value="">General Project</option>';

            const milestones = Array.isArray(data.milestones)
                ? data.milestones
                : [];

            milestones.forEach(function (milestone) {
                const option = document.createElement("option");

                option.value = milestone.id;

                option.textContent =
                    milestone.title +
                    " — " +
                    milestone.status;

                if (
                    selectedMilestoneId &&
                    String(milestone.id) ===
                    String(selectedMilestoneId)
                ) {
                    option.selected = true;
                }

                milestoneSelect.appendChild(option);
            });

            milestoneSelect.disabled = false;

        } catch (error) {
            console.error(
                "Unable to load milestones:",
                error
            );

            milestoneSelect.innerHTML =
                '<option value="">Unable to load milestones</option>';

            milestoneSelect.disabled = true;
        }
    }

    /*
     * CLIENT → PROPOSAL
     */
    clientSelect.addEventListener(
        "change",
        function () {
            const clientId = this.value;

            /*
             * Changing client must clear both downstream fields.
             */
            resetProposals("Loading proposals...");
            resetMilestones();

            if (!clientId) {
                resetProposals();
                return;
            }

            loadProposals(clientId);
        }
    );

    /*
     * PROPOSAL → MILESTONE
     */
    proposalSelect.addEventListener(
        "change",
        function () {
            const proposalId = this.value;

            resetMilestones("Loading milestones...");

            if (!proposalId) {
                resetMilestones();
                return;
            }

            loadMilestones(proposalId);
        }
    );

    /*
     * INITIAL LOAD
     *
     * When editing an existing ProposalUpdate,
     * restore:
     *
     * Client
     *   ↓
     * Proposal
     *   ↓
     * Milestone
     */
    if (clientSelect.value) {
        loadProposals(
            clientSelect.value,
            originalProposalId
        );
    } else {
        resetProposals();
        resetMilestones();
    }
});