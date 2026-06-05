module.exports = function (api) {
  api.cache(true);
  return {
    presets: ["babel-preset-expo"],
    plugins: [
      // Explicitly transform private class fields (#field) and private methods
      // so Hermes receives standard JS regardless of which node_module emits them.
      ["@babel/plugin-transform-class-properties", { loose: true }],
      ["@babel/plugin-transform-private-methods",  { loose: true }],
    ],
  };
};
