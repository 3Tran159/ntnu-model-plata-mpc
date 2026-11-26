function godo_view(runsDir, names)
%GODO_VIEW  Interactive comparison of Godo-control STAR-CCM+ runs (history.csv from GodoControl.java).
%   godo_view                         -> all cases in T:\NTNU_GODO_CONTROL_20261109\30_runs
%   godo_view([], {'FIXED_LONG','MAP_FF','MAP_FF180'})  -> newest case of each prefix
%
% Columns (SI, as written by the macro): time_s, CL, CD, Fx_N, Fz_N, Mh_Nm, pFlapAbsMin_Pa,
%   cmd_deg, meas_deg, interfaceCFL, eta_m3_m (gauge x=-3 m), eta_hinge_m (x=0.952 m), trim_deg
% Hinge power (sign convention still to be confirmed): P = -Mh * d(delta)/dt [W]
% Axes are linked in time; zoom/pan, data tips; click a legend entry to hide/show a line.
% Works while runs are still going (reads what is written so far).

if nargin < 1 || isempty(runsDir), runsDir = 'T:\NTNU_GODO_CONTROL_20261109\30_runs'; end
if nargin < 2 || isempty(names)
    d = dir(fullfile(runsDir, '*_2026*'));
    d = d([d.isdir]);
    names = unique(regexprep({d.name}, '_\d{8}_\d{6}$', ''));
end

cases = struct('name', {}, 'T', {});
for k = 1:numel(names)
    d = dir(fullfile(runsDir, [names{k} '_2026*']));
    d = d([d.isdir]);
    if isempty(d), continue; end
    [~, i] = max([d.datenum]);
    f = fullfile(runsDir, d(i).name, 'history.csv');
    if ~isfile(f), continue; end
    T = readtable(f);
    T = T(all(isfinite(T{:, {'time_s','CL','CD'}}), 2), :);   % drop a partially written last line
    if height(T) < 3, continue; end
    cases(end+1) = struct('name', names{k}, 'T', T); %#ok<AGROW>
end
if isempty(cases), error('No history.csv found'); end

fig = figure('Name', 'Godo control runs', 'Color', 'w');
tl = tiledlayout(fig, 6, 1, 'TileSpacing', 'compact');
ttl = {'\eta(x=-3 m) [m]', '\delta [deg] (cmd solid, meas dashed)', 'C_L', 'C_D', ...
       'M_h [N m]', '-M_h d\delta/dt [W]'};
ax = gobjects(6, 1);
for j = 1:6
    ax(j) = nexttile(tl); hold(ax(j), 'on'); grid(ax(j), 'on'); ylabel(ax(j), ttl{j});
end
for k = 1:numel(cases)
    T = cases(k).T; t = T.time_s; n = strrep(cases(k).name, '_', '\_');
    if ismember('eta_m3_m', T.Properties.VariableNames), plot(ax(1), t, T.eta_m3_m, 'DisplayName', n); end
    h = plot(ax(2), t, T.cmd_deg, 'DisplayName', [n ' cmd']);
    plot(ax(2), t, T.meas_deg, '--', 'Color', h.Color, 'DisplayName', [n ' meas']);
    plot(ax(3), t, T.CL, 'DisplayName', n);
    plot(ax(4), t, T.CD, 'DisplayName', n);
    plot(ax(5), t, T.Mh_Nm, 'DisplayName', n);
    plot(ax(6), t, -T.Mh_Nm .* gradient(deg2rad(T.meas_deg), t), 'DisplayName', n);
end
for j = 1:6
    lg = legend(ax(j), 'Location', 'eastoutside');
    lg.ItemHitFcn = @toggleLine;
end
xlabel(ax(6), 't [s]');
linkaxes(ax, 'x');
end

function toggleLine(~, evt)
if strcmp(evt.Peer.Visible, 'on'), evt.Peer.Visible = 'off'; else, evt.Peer.Visible = 'on'; end
end
